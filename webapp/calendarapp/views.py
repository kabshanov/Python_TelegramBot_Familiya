from django.http import HttpResponse

def healthcheck(request):
    return HttpResponse("Calendar WebApp is running.")
