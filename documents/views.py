import logging
import os
import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, Http404
from django.db.models import Q, Sum
from .models import Document
from .forms import DocumentUploadForm, DocumentEditForm
from .services.crypto_service import VaultDecryptionError

logger = logging.getLogger(__name__)


@login_required(login_url='login')
def documents_list_view(request):
    """
    Personal Document Vault List view.
    Supports domain category filtering, text search, and real-time vault stats.
    """
    documents = Document.objects.filter(user=request.user)
    
    # Category filter
    selected_category = request.GET.get('category', '').strip().lower()
    if selected_category and selected_category != 'all':
        documents = documents.filter(category=selected_category)

    # Search filter
    search_query = request.GET.get('q', '').strip()
    if search_query:
        documents = documents.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(original_filename__icontains=search_query)
        )

    # Sorting
    sort_by = request.GET.get('sort', '-created_at')
    valid_sorts = ['-created_at', 'created_at', 'title', '-file_size', 'file_size']
    if sort_by in valid_sorts:
        documents = documents.order_by(sort_by)

    # Calculate overall storage for this user
    all_user_docs = Document.objects.filter(user=request.user)
    total_bytes = all_user_docs.aggregate(total=Sum('file_size'))['total'] or 0
    total_mb = total_bytes / (1024 * 1024)

    # Category counts
    category_counts = {
        'all': all_user_docs.count(),
        'medical': all_user_docs.filter(category='medical').count(),
        'education': all_user_docs.filter(category='education').count(),
        'vehicle': all_user_docs.filter(category='vehicle').count(),
        'personal': all_user_docs.filter(category='personal').count(),
        'professional': all_user_docs.filter(category='professional').count(),
        'other': all_user_docs.filter(category='other').count(),
    }

    context = {
        'documents': documents,
        'selected_category': selected_category or 'all',
        'search_query': search_query,
        'sort_by': sort_by,
        'total_count': all_user_docs.count(),
        'total_mb': f"{total_mb:.1f}",
        'category_counts': category_counts,
    }
    return render(request, 'documents/list.html', context)


@login_required(login_url='login')
def documents_upload_view(request):
    """Secure document upload handler."""
    next_url = request.GET.get('next') or request.POST.get('next')

    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                document = form.save(commit=False)
                document.user = request.user
                document.save()
                messages.success(request, f"Document '{document.title}' encrypted and stored in your vault.")
                if next_url == 'share_create':
                    return redirect(f"{reverse('share_create')}?doc={document.pk}")
                return redirect('document_detail', pk=document.pk)
            except Exception as e:
                logger.error(f"Error saving uploaded document: {e}", exc_info=True)
                messages.error(request, f"An error occurred while saving the document: {str(e)}")
    else:
        # Pre-select category from query param if provided
        initial_category = request.GET.get('category', 'other')
        form = DocumentUploadForm(initial={'category': initial_category})

    return render(request, 'documents/upload.html', {'form': form, 'next': next_url})


@login_required(login_url='login')
def document_detail_view(request, pk):
    """
    Document detail & metadata inspector.
    Displays SHA-256 hash, file properties, and safe in-browser preview.
    Protected against IDOR: only the document owner can inspect.
    """
    document = get_object_or_404(Document, pk=pk, user=request.user)
    return render(request, 'documents/detail.html', {'document': document})


@login_required(login_url='login')
def document_preview_view(request, pk):
    """
    Secure in-browser document preview stream.
    Protected against IDOR: only the document owner can preview.
    Decrypts AES-256-GCM vault payload in-memory and renders inline (PDF/PNG/JPG).
    """
    document = get_object_or_404(Document, pk=pk, user=request.user)
    
    if not document.file:
        raise Http404("Document file could not be found.")

    try:
        content_bytes = document.get_decrypted_content()
    except (FileNotFoundError, OSError, ValueError):
        raise Http404("Document file could not be opened on storage.")
    except VaultDecryptionError:
        raise Http404("Document content corrupted or cryptographic verification failed.")

    filename = document.original_filename or f"{document.title}{os.path.splitext(document.file.name)[1]}"
    response = FileResponse(
        io.BytesIO(content_bytes),
        as_attachment=False,
        filename=filename,
        content_type=document.file_type or 'application/octet-stream'
    )
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response['Pragma'] = 'no-cache'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required(login_url='login')
def document_download_view(request, pk):
    """
    Secure document download stream.
    Protected against IDOR: only the document owner can download.
    Decrypts AES-256-GCM vault payload in-memory and streams attachment.
    """
    document = get_object_or_404(Document, pk=pk, user=request.user)
    
    if not document.file:
        raise Http404("Document file could not be found.")

    try:
        content_bytes = document.get_decrypted_content()
    except (FileNotFoundError, OSError, ValueError):
        raise Http404("Document file could not be opened on storage.")
    except VaultDecryptionError:
        raise Http404("Document content corrupted or cryptographic verification failed.")

    download_filename = document.original_filename or f"{document.title}{os.path.splitext(document.file.name)[1]}"
    response = FileResponse(
        io.BytesIO(content_bytes),
        as_attachment=True,
        filename=download_filename,
        content_type=document.file_type or 'application/octet-stream'
    )
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response['Pragma'] = 'no-cache'
    response['X-Content-Type-Options'] = 'nosniff'
    return response



@login_required(login_url='login')
def document_edit_view(request, pk):
    """Edit document metadata without modifying file content."""
    document = get_object_or_404(Document, pk=pk, user=request.user)

    if request.method == 'POST':
        form = DocumentEditForm(request.POST, instance=document)
        if form.is_valid():
            form.save()
            messages.success(request, f"Document '{document.title}' updated successfully.")
            return redirect('document_detail', pk=document.pk)
    else:
        form = DocumentEditForm(instance=document)

    return render(request, 'documents/edit.html', {'form': form, 'document': document})


@login_required(login_url='login')
def document_delete_view(request, pk):
    """
    Delete document and sanitize physical disk file.
    Protected against IDOR: only the document owner can delete.
    """
    document = get_object_or_404(Document, pk=pk, user=request.user)

    if request.method == 'POST':
        title = document.title
        # Delete file from disk
        if document.file and os.path.exists(document.file.path):
            try:
                os.remove(document.file.path)
            except OSError:
                pass
        document.delete()
        messages.success(request, f"Document '{title}' was permanently deleted from your vault.")
        return redirect('documents_list')

    return render(request, 'documents/confirm_delete.html', {'document': document})
