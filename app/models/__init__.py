# Re-export models so that `from app.models import User, Project` works
# and so Alembic's env.py can import this package to register all metadata.
from app.models.user import User
from app.models.project import Project

__all__ = ["User", "Project"]
