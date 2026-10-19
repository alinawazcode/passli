from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_view, name='landing'),
    path('register/', views.register_view, name='register'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # Password Recovery Workflows
    path('password-reset/', views.password_reset_request_view, name='password_reset'),
    path('password-reset/confirm/<str:token>/', views.password_reset_confirm_view, name='password_reset_confirm'),

    # Email Verification & OTP Workflows
    path('verify-email/', views.verify_email_view, name='verify_email'),
    path('verify-email/resend/', views.resend_verification_otp_view, name='resend_verification_otp'),
]
