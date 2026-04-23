class RecaptchaSolverError(Exception):
    pass


class CaptchaNotFoundError(RecaptchaSolverError):
    pass


class ElementNotFoundError(RecaptchaSolverError):
    pass


class LowConfidenceError(RecaptchaSolverError):
    pass


class TokenExtractionError(RecaptchaSolverError):
    pass


class UnsupportedCaptchaError(RecaptchaSolverError):
    pass
