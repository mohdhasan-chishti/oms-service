import pymysql
from contextlib import contextmanager
from app.config.settings import OMSConfigs
from app.logging.utils import get_app_logger

configs = OMSConfigs()
logger = get_app_logger("app.mariadb_connection")

class MariaDBConnection:
    def __init__(self):
        self.url = configs.MARIADB_DATABASE_URL
        if not self.url:
            logger.error("mariadb_url_missing")
            raise ValueError("MARIADB_DATABASE_URL not configured")

    def _parse(self):
        u = self.url.replace("mysql://", "", 1)
        auth, hostdb = u.split("@", 1)
        user, password = auth.split(":", 1)
        hostport, database = hostdb.split("/", 1)
        if ":" in hostport:
            host, port = hostport.split(":", 1)
            port = int(port)
        else:
            host, port = hostport, 3306
        return {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "charset": "utf8mb4",
            "autocommit": True,
        }

    @contextmanager
    def get_connection(self):
        conn = None
        try:
            params = self._parse()
            conn = pymysql.connect(**params)
            yield conn
        except Exception as e:
            logger.error(f"mariadb_connection_error | host={params.get('host')} db={params.get('database')} error={e}", exc_info=True)
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

mariadb_connection = MariaDBConnection()
