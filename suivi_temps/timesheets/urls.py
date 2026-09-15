from django.urls import path
from . import views

urlpatterns = [
    path('logout/', views.custom_logout, name='logout'),
    path('', views.timesheet_list, name='timesheet_list'),
    path('weekly-summary/', views.timesheet_weekly_summary, name='timesheet_weekly_summary'),
    path('timesheet/new/', views.timesheet_create, name='timesheet_create'),
    path('timesheet/<int:pk>/', views.timesheet_detail, name='timesheet_detail'),
    path('report/pdf/<str:monday>/', views.generate_pdf_report, name='generate_pdf_report'),
    path('report/word/<str:monday>/', views.generate_word_report, name='generate_word_report'),
]