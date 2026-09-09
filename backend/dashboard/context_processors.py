def accessiq_context(request):
    """
    Context processor to provide global branding and navigation context.
    """
    return {
        'APP_NAME': 'AccessIQ',
        'APP_SUBTITLE': 'Smart Campus Identity, Access & Security Management System',
        'SYSTEM_VERSION': '2.0.0',
    }
