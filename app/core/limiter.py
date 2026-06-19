# Dummy limiter para evitar errores de conexión a Redis
class DummyLimiter:
    def limit(self, *args, **kwargs):
        def wrapper(func):
            return func
        return wrapper

limiter = DummyLimiter()