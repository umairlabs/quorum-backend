from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .serializers import (
    AISuggestionsOutputSerializer,
    GenerateMaintenanceIssueSerializer,
    GeneratedMaintenanceIssueSerializer,
    AIChatInputSerializer,
    AIChatOutputSerializer,
    AIExecuteActionSerializer,
    AIActionResultSerializer,
)
from .services import (
    get_ai_suggestions,
    generate_maintenance_issue,
    process_ai_chat,
    execute_ai_action,
)


class GenerateMaintenanceIssueView(APIView):
    """
    POST /api/ai/generate-maintenance-issue/
    Accepts a short user prompt and returns AI-generated maintenance issue fields.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = GenerateMaintenanceIssueSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        prompt = serializer.validated_data["prompt"]
        result = generate_maintenance_issue(prompt)

        out = GeneratedMaintenanceIssueSerializer(data=result)
        if not out.is_valid():
            return Response(
                {"title": "General Hardware Issue", "description": "An issue has been reported that requires IT assessment.", "priority": "MEDIUM"},
                status=status.HTTP_200_OK,
            )

        return Response(out.data, status=status.HTTP_200_OK)


class AIChatView(APIView):
    """
    POST /api/ai/chat/
    Main AI Asset Assistant chat endpoint.
    Accepts natural language user query and optional conversation history.
    Returns AI response message, intent, and optional action proposal.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = AIChatInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        message = serializer.validated_data["message"]
        history = serializer.validated_data.get("conversation_history", [])

        res = process_ai_chat(user=request.user, message=message, conversation_history=history)

        out = AIChatOutputSerializer(data=res)
        if not out.is_valid():
            return Response(
                {
                    "message": res.get("message", "Processed request."),
                    "intent": res.get("intent", "QUERY"),
                    "action": res.get("action", None)
                },
                status=status.HTTP_200_OK
            )

        return Response(out.data, status=status.HTTP_200_OK)


class AIExecuteActionView(APIView):
    """
    POST /api/ai/execute-action/
    Executes an action proposed by the AI Assistant after user confirmation.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = AIExecuteActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        action_type = serializer.validated_data["action_type"]
        params = serializer.validated_data.get("params", {})

        result = execute_ai_action(user=request.user, action_type=action_type, params=params)

        out = AIActionResultSerializer(data=result)
        if not out.is_valid():
            return Response(result, status=status.HTTP_200_OK)

        return Response(out.data, status=status.HTTP_200_OK)


class AISuggestionsView(APIView):
    """
    GET /api/ai/suggestions/
    Returns dynamic, real-database-driven prompt suggestions for the AI Chat Assistant.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        suggestions = get_ai_suggestions(user=request.user)
        out = AISuggestionsOutputSerializer(data={"suggestions": suggestions})
        if out.is_valid():
            return Response(out.data, status=status.HTTP_200_OK)
        return Response({"suggestions": suggestions}, status=status.HTTP_200_OK)
