"""The app module, containing the app factory function."""

import logging
import connexion
from connexion.resolver import RestyResolver
from flask_jwt import JWT

from src.settings import ProductionConfig
from src.extensions import cors, db
from src.auth import authenticate, identity


def create_app(config = ProductionConfig):
	"""An application factory, as explained here:
	http://flask.pocoo.org/docs/patterns/appfactories/.

	:param config: The configuration object to use.
	"""
	connexion_app = connexion.FlaskApp(__name__)
	connexion_app.app.config.from_object(config)

	app = connexion_app.app

	register_extensions(app)
	register_logger(app, config)
	register_routes(connexion_app)

	return app


def register_extensions(app):
	"""Register Flask extensions."""
	cors.init_app(app)
	db.init_app(app)
	JWT(app, authenticate, identity)


def register_logger(app, config):
	"""Register logging handlers."""
	# Set up logging to file
	logging.basicConfig(
		filename = 'dfn-gui-server.log',
		level = config.LOGGING_LEVEL,
		format = '[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
		datefmt = '%H:%M:%S'
	)

	# Set up logging to console
	console = logging.StreamHandler()

	console.setLevel(config.LOGGING_LEVEL)
	console.setFormatter(logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s'))

	logging.getLogger('').addHandler(console)
	logging.getLogger('flask_cors').level = config.CORS_LOGGING_LEVEL


def register_routes(app):
	"""Register swagger api endpoints."""
	app.add_api('api/network/swagger.yaml')
	app.add_api('api/session/swagger.yaml')
