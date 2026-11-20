from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from datetime import date

from .serializers import DashboardSummarySerializer
from .services import DashboardService

class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_from = None
        date_to = None

        date_from_str = request.query_params.get('date_from')
        date_to_str = request.query_params.get('date_to')

        try:
            if date_from_str:
                date_from = date.fromisoformat(date_from_str)
            if date_to_str:
                date_to = date.fromisoformat(date_to_str)
        except ValueError:
            return Response(
                {'detail': 'Invalid date format. Use YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = DashboardService.get_dashboard_summary(
            user=request.user,
            date_from=date_from,
            date_to=date_to
        )
        serializer = DashboardSummarySerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
