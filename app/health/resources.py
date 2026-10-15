from flask_restful import Resource


class HealthResource(Resource):
    """Usado por el health check de Beanstalk; no requiere token."""

    def get(self):
        return {"status": "ok"}, 200
