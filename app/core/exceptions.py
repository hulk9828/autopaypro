from fastapi import HTTPException, status


class AppException:
    """Class-based exception handlers for common HTTP status codes."""
    
    @staticmethod
    def raise_400(message: str = "Bad Request"):
        """Raise a 400 Bad Request exception."""
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    
    @staticmethod
    def raise_401(message: str = "Unauthorized"):
        """Raise a 401 Unauthorized exception."""
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)
    
    @staticmethod
    def raise_403(message: str = "Forbidden"):
        """Raise a 403 Forbidden exception."""
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)
    
    @staticmethod
    def raise_404(message: str = "Not Found"):
        """Raise a 404 Not Found exception."""
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
    
    @staticmethod
    def raise_500(message: str = "Internal Server Error"):
        """Raise a 500 Internal Server Error exception."""
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


# Create an instance for convenience
app_exception = AppException()

# For backward compatibility, provide direct access to methods
raise_400 = AppException.raise_400
raise_401 = AppException.raise_401
raise_403 = AppException.raise_403
raise_404 = AppException.raise_404
raise_500 = AppException.raise_500
