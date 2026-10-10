import logging
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.urls import reverse
from django.utils import timezone
from .models import SharePass
from .forms import RecipientKeyVerificationForm
from audit.models import ShareAccessLog, log_share_event

logger = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 5


def _session_auth_key(pass_id) -> str:
    return f"recipient_authenticated_{str(pass_id)}"


def _session_failures_key(pass_id) -> str:
    return f"recipient_failures_{str(pass_id)}"


def recipient_verify_view(request, pass_id):
    """
    Public entry point for QR scan & direct link access (`/p/<uuid:pass_id>/`).
    Evaluates pass lifecycle (revoked, expired, max uses, rate-limiting lockout).
    Prompts recipient for 8-character Share Key and verifies against PBKDF2 hash.
    """
    share_pass = get_object_or_404(
        SharePass.objects.prefetch_related('documents'),
        id=pass_id
    )

    auth_key = _session_auth_key(pass_id)
    fail_key = _session_failures_key(pass_id)

    # 1. Check owner revocation
    if share_pass.is_revoked:
        request.session.pop(auth_key, None)
        log_share_event(
            share_pass,
            ShareAccessLog.EventType.PASS_REVOKED,
            request=request,
            status=ShareAccessLog.Status.REVOKED,
            details='Access attempt on revoked pass'
        )
        return render(request, 'sharing/recipient_error.html', {
            'pass': share_pass,
            'status': 'revoked',
            'title': 'Access Pass Revoked',
            'error_message': 'The vault owner has immediately terminated access to this Share Pass. No files can be viewed or downloaded.',
        }, status=403)

    # 2. Check time expiration
    if share_pass.is_expired():
        request.session.pop(auth_key, None)
        log_share_event(
            share_pass,
            ShareAccessLog.EventType.PASS_EXPIRED,
            request=request,
            status=ShareAccessLog.Status.EXPIRED,
            details='Access attempt on expired pass'
        )
        return render(request, 'sharing/recipient_error.html', {
            'pass': share_pass,
            'status': 'expired',
            'title': 'Access Pass Expired',
            'error_message': f'This time-gated Share Pass expired on {share_pass.expires_at.strftime("%b %d, %Y at %H:%M UTC") if share_pass.expires_at else "its expiration timer"}.',
        }, status=410)

    # 3. Check single-use / usage limit
    if share_pass.is_limit_reached() and not request.session.get(auth_key):
        log_share_event(
            share_pass,
            ShareAccessLog.EventType.RATE_LOCKED,
            request=request,
            status=ShareAccessLog.Status.LOCKED,
            details=f'Usage limit reached ({share_pass.access_count}/{share_pass.max_uses})'
        )
        return render(request, 'sharing/recipient_error.html', {
            'pass': share_pass,
            'status': 'limit_reached',
            'title': 'Usage Limit Reached',
            'error_message': f'This single-use Share Pass has already reached its maximum limit of {share_pass.max_uses} access session(s).',
        }, status=410)

    # 4. Check brute-force lockout
    failures = request.session.get(fail_key, 0)
    if failures >= MAX_FAILED_ATTEMPTS:
        log_share_event(
            share_pass,
            ShareAccessLog.EventType.RATE_LOCKED,
            request=request,
            status=ShareAccessLog.Status.LOCKED,
            details=f'Brute-force limit reached ({failures}/{MAX_FAILED_ATTEMPTS})'
        )
        return render(request, 'sharing/recipient_error.html', {
            'pass': share_pass,
            'status': 'locked',
            'title': 'Access Temporarily Locked',
            'error_message': f'Too many failed key verification attempts ({failures}/{MAX_FAILED_ATTEMPTS}). For cryptographic security, access is temporarily locked for this browser.',
        }, status=429)

    # 5. If already authenticated in session, forward straight to document portal
    if request.session.get(auth_key):
        return redirect('recipient_portal', pass_id=share_pass.id)

    # 6. Process key submission
    remaining_attempts = MAX_FAILED_ATTEMPTS - failures

    if request.method == 'POST':
        form = RecipientKeyVerificationForm(request.POST)
        if form.is_valid():
            submitted_key = form.cleaned_data['access_key']
            if share_pass.verify_key(submitted_key):
                # Valid key! Reset failure counter and establish ephemeral session
                request.session.pop(fail_key, None)
                request.session[auth_key] = True

                # Record access event count
                share_pass.access_count += 1
                share_pass.save(update_fields=['access_count', 'updated_at'])

                log_share_event(
                    share_pass,
                    ShareAccessLog.EventType.KEY_SUCCESS,
                    request=request,
                    status=ShareAccessLog.Status.SUCCESS,
                    details='Share Key successfully verified'
                )

                return redirect('recipient_portal', pass_id=share_pass.id)
            else:
                failures += 1
                request.session[fail_key] = failures
                remaining_attempts = max(0, MAX_FAILED_ATTEMPTS - failures)

                log_share_event(
                    share_pass,
                    ShareAccessLog.EventType.KEY_FAILED,
                    request=request,
                    status=ShareAccessLog.Status.DENIED,
                    details=f'Invalid key submitted ({failures}/{MAX_FAILED_ATTEMPTS})'
                )

                if failures >= MAX_FAILED_ATTEMPTS:
                    log_share_event(
                        share_pass,
                        ShareAccessLog.EventType.RATE_LOCKED,
                        request=request,
                        status=ShareAccessLog.Status.LOCKED,
                        details='Maximum invalid key attempts reached'
                    )
                    return render(request, 'sharing/recipient_error.html', {
                        'pass': share_pass,
                        'status': 'locked',
                        'title': 'Access Temporarily Locked',
                        'error_message': f'Maximum invalid attempts reached ({failures}/{MAX_FAILED_ATTEMPTS}). Access is locked.',
                    }, status=429)

                form.add_error(
                    'access_key',
                    f"Invalid Share Key. {remaining_attempts} attempt(s) remaining before security lockout."
                )
        else:
            failures += 1
            request.session[fail_key] = failures
            remaining_attempts = max(0, MAX_FAILED_ATTEMPTS - failures)

            log_share_event(
                share_pass,
                ShareAccessLog.EventType.KEY_FAILED,
                request=request,
                status=ShareAccessLog.Status.DENIED,
                details=f'Invalid key format submitted ({failures}/{MAX_FAILED_ATTEMPTS})'
            )

            if failures >= MAX_FAILED_ATTEMPTS:
                log_share_event(
                    share_pass,
                    ShareAccessLog.EventType.RATE_LOCKED,
                    request=request,
                    status=ShareAccessLog.Status.LOCKED,
                    details='Maximum invalid key attempts reached'
                )
                return render(request, 'sharing/recipient_error.html', {
                    'pass': share_pass,
                    'status': 'locked',
                    'title': 'Access Temporarily Locked',
                    'error_message': f'Maximum invalid attempts reached ({failures}/{MAX_FAILED_ATTEMPTS}). Access is locked.',
                }, status=429)
    else:
        form = RecipientKeyVerificationForm()

    context = {
        'pass': share_pass,
        'form': form,
        'remaining_attempts': remaining_attempts,
        'max_attempts': MAX_FAILED_ATTEMPTS,
        'documents_count': share_pass.documents.count(),
    }
    return render(request, 'sharing/recipient_verify.html', context)


def recipient_portal_view(request, pass_id):
    """
    Authorized recipient document console.
    Renders the active document preview, document selector, expiration countdown,
    and download buttons (if permitted).
    """
    share_pass = get_object_or_404(
        SharePass.objects.prefetch_related('documents'),
        id=pass_id
    )

    auth_key = _session_auth_key(pass_id)

    # Enforce session authentication
    if not request.session.get(auth_key):
        return redirect('recipient_verify', pass_id=share_pass.id)

    # Check pass status (instant revocation check)
    if share_pass.is_revoked:
        request.session.pop(auth_key, None)
        return render(request, 'sharing/recipient_error.html', {
            'pass': share_pass,
            'status': 'revoked',
            'title': 'Access Pass Revoked',
            'error_message': 'The vault owner has revoked this Share Pass. Access terminated.',
        }, status=403)

    if share_pass.is_expired():
        request.session.pop(auth_key, None)
        return render(request, 'sharing/recipient_error.html', {
            'pass': share_pass,
            'status': 'expired',
            'title': 'Access Pass Expired',
            'error_message': 'This Share Pass has reached its expiration timestamp.',
        }, status=410)

    documents = list(share_pass.documents.all())
    if not documents:
        raise Http404("No documents found in this Share Pass.")

    # Select document to view
    selected_doc_id = request.GET.get('doc')
    active_doc = None
    if selected_doc_id:
        try:
            active_doc = next((d for d in documents if str(d.id) == str(selected_doc_id)), None)
        except (ValueError, TypeError):
            active_doc = None

    if not active_doc:
        active_doc = documents[0]

    # Extract client IP and access timestamp for dynamic anti-exfiltration watermarking
    from audit.models import get_client_ip
    client_ip = get_client_ip(request) or '127.0.0.1'
    access_time = timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    pass_short_id = str(share_pass.id)[:8].upper()
    watermark_label = f"CONFIDENTIAL • PASSLI #{pass_short_id} • {client_ip} • {access_time}"

    context = {
        'pass': share_pass,
        'documents': documents,
        'active_doc': active_doc,
        'can_download': share_pass.can_download,
        'expires_at_iso': share_pass.expires_at.isoformat() if share_pass.expires_at else '',
        'client_ip': client_ip,
        'access_timestamp': access_time,
        'pass_short_id': pass_short_id,
        'watermark_label': watermark_label,
    }
    return render(request, 'sharing/recipient_portal.html', context)


def recipient_doc_preview_view(request, pass_id, doc_id):
    """
    Secure in-browser document preview stream for verified recipients.
    Protects against IDOR: document must belong to this specific Share Pass,
    and recipient must hold an active verified session.
    """
    share_pass = get_object_or_404(SharePass, id=pass_id)
    auth_key = _session_auth_key(pass_id)

    if not request.session.get(auth_key):
        return HttpResponseForbidden("Recipient authorization required.")

    if share_pass.is_revoked or share_pass.is_expired():
        return HttpResponseForbidden("Share Pass is no longer active.")

    # IDOR Check: Ensure document is attached to this pass
    doc = share_pass.documents.filter(id=doc_id).first()
    if not doc or not doc.file:
        raise Http404("Document record not found in this Share Pass.")

    try:
        file_obj = doc.file.open('rb')
    except (FileNotFoundError, OSError, ValueError):
        raise Http404("Document file could not be opened from storage.")

    ext = os.path.splitext(doc.file.name)[1]
    filename = doc.original_filename or f"{doc.title}{ext}"

    log_share_event(
        share_pass,
        ShareAccessLog.EventType.VIEW_DOC,
        request=request,
        document=doc,
        status=ShareAccessLog.Status.SUCCESS,
        details=f"Preview stream: {doc.title}"
    )

    response = FileResponse(
        file_obj,
        as_attachment=False,
        filename=filename,
        content_type=doc.file_type or 'application/octet-stream'
    )
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response['Pragma'] = 'no-cache'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def recipient_doc_download_view(request, pass_id, doc_id):
    """
    Secure document download stream for verified recipients.
    Enforces `can_download=True` permission set by the pass owner.
    """
    share_pass = get_object_or_404(SharePass, id=pass_id)
    auth_key = _session_auth_key(pass_id)

    if not request.session.get(auth_key):
        return HttpResponseForbidden("Recipient authorization required.")

    if share_pass.is_revoked or share_pass.is_expired():
        return HttpResponseForbidden("Share Pass is no longer active.")

    # Strict Permission Check
    if not share_pass.can_download:
        return HttpResponseForbidden("Raw file download is disabled for this Share Pass by the owner.")

    # IDOR Check: Ensure document is attached to this pass
    doc = share_pass.documents.filter(id=doc_id).first()
    if not doc or not doc.file:
        raise Http404("Document record not found in this Share Pass.")

    try:
        file_obj = doc.file.open('rb')
    except (FileNotFoundError, OSError, ValueError):
        raise Http404("Document file could not be opened from storage.")

    ext = os.path.splitext(doc.file.name)[1]
    download_filename = doc.original_filename or f"{doc.title}{ext}"

    log_share_event(
        share_pass,
        ShareAccessLog.EventType.DOWNLOAD_DOC,
        request=request,
        document=doc,
        status=ShareAccessLog.Status.SUCCESS,
        details=f"Downloaded: {doc.title}"
    )

    response = FileResponse(
        file_obj,
        as_attachment=True,
        filename=download_filename,
        content_type=doc.file_type or 'application/octet-stream'
    )
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response['Pragma'] = 'no-cache'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def recipient_leave_view(request, pass_id):
    """
    Explicitly terminates the recipient inspection session and clears all session tokens.
    """
    share_pass = get_object_or_404(SharePass, id=pass_id)
    auth_key = _session_auth_key(pass_id)
    request.session.pop(auth_key, None)

    log_share_event(
        share_pass,
        ShareAccessLog.EventType.SESSION_LEFT,
        request=request,
        status=ShareAccessLog.Status.SUCCESS,
        details="Recipient voluntarily ended session"
    )

    return render(request, 'sharing/recipient_error.html', {
        'pass': share_pass,
        'status': 'left',
        'title': 'Session Securely Closed',
        'error_message': 'You have successfully exited this document inspection session. All in-browser decrypted session references have been cleared.',
    })

