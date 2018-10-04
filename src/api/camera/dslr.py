from src.wrappers import jwt, endpoint, current_app_injector, logger
from src.console import console


__all__ = ['get', 'on', 'off']


@logger('Checking status of DSLR camera.')
@current_app_injector
def _status(log):
	status = False

	if 'Nikon Corp.' in console('lsusb'):
		status = True

	log.debug('DSLR Camera Status: {}'.format(status))

	return status


@jwt
@endpoint
@current_app_injector
def get(handler):
	handler.add_to_success_response(status = _status())


@jwt
@logger('Enabling DSLR camera.')
@endpoint
@current_app_injector
def on(handler):
	console('python /opt/dfn-software/enable_camera.py')
	handler.add_to_success_response(status = _status())


@jwt
@logger('Disabling DSLR camera.')
@endpoint
@current_app_injector
def off(handler):
	console('python /opt/dfn-software/disable_camera.py')
	handler.add_to_success_response(status = _status())
