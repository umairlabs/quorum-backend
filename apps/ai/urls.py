from django.urls import path
from .views import GenerateMaintenanceIssueView, AIChatView, AIExecuteActionView, AISuggestionsView

app_name = 'ai'

urlpatterns = [
    path('suggestions/', AISuggestionsView.as_view(), name='ai-suggestions'),
    path('generate-maintenance-issue/', GenerateMaintenanceIssueView.as_view(), name='generate-maintenance-issue'),
    path('chat/', AIChatView.as_view(), name='ai-chat'),
    path('execute-action/', AIExecuteActionView.as_view(), name='ai-execute-action'),
]
