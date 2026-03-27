from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# In-memory storage is fine for a single-server deployment.
# With multiple gunicorn workers each worker has its own counter,
# meaning the effective limit is limit * workers.
# For a small internal app this is acceptable.
limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
