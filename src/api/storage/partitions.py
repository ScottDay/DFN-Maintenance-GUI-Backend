from json import loads
from re import sub, split
from subprocess import CalledProcessError

import src.wrappers as wrappers
from src.console import console


def _filter_out_empty_entries(devices):
	result = []

	# Ignore devices without a number.
	for line in devices:
		split_line = line.split(' ')
		tmp = []

		if any(char.isdigit() for char in split_line[0]):
			for col in split_line:
				if len(col) > 0:
					tmp.append(col)

			result.append(tmp)

	return result


def _to_json(devices):
	result = []

	for line in devices:
		if len(line) is 5:
			entry = {
				'name': line[0],
				'label': line[1],
				'size': line[2],
				'fstype': line[3],
				'mountpoint': line[4]
			}
		else:
			entry = {
				'name': line[0],
				'label': None,
				'size': '',
				'fstype': '',
				'mountpoint': None
			}

			if line[1][0].isdigit() and line[1][-1].isalpha():
				entry['size'] = line[1]

				if len(line) > 3:
					if '/' not in line[2]:
						entry['fstype'] = line[2]

						if len(line) == 4:
							entry['mountpoint'] = line[3]
					else:
						entry['mountpoint'] = line[2]
			else:
				entry['label'] = line[1]

				if line[2][0].isdigit() and line[2][-1].isalpha():
					entry['size'] = line[2]

					if '/' not in line[3]:
						entry['fstype'] = line[3]

						if len(line) == 5:
							entry['mountpoint'] = line[4]
					else:
						entry['mountpoint'] = line[3]
				elif '/' not in line[3]:
					entry['fstype'] = line[3]

					if len(line) == 5:
						entry['mountpoint'] = line[4]
				else:
					entry['mountpoint'] = line[3]

		result.append(entry)

	return result


@wrappers.logger('Loading raw lsblk devices.')
def _lsblk_no_json():
	devices = console('lsblk --list --noheadings --output NAME,LABEL,SIZE,FSTYPE,MOUNTPOINT').splitlines()
	devices = _filter_out_empty_entries(devices)

	return _to_json(devices)


@wrappers.logger('Loading lsblk devices.')
def _lsblk_with_json():
	return loads(console('lsblk --inverse --nodeps --json --output NAME,LABEL,SIZE,FSTYPE,MOUNTPOINT'))['blockdevices']


@wrappers.logger('Loading fs devices.')
@wrappers.injector
def _list_fs_devices(log):
	# Load mounted / on devices.
	try:
		output = _lsblk_with_json()
	except CalledProcessError:
		log.warning('This version of lsblk does not offer json output, switching to raw parsing.')
		output = _lsblk_no_json()

	devices = []

	# Filter out devices without a label i.e. data0 (except root '/').
	for device in output:
		if '/dev/' not in device['name']:
			device['name'] = '/dev/{0}'.format(device['name'])

		if device['label'] is None and device['mountpoint'] is '/':
			device['label'] = ''

		if device['label'] is not None:
			devices.append(device)

	return devices


@wrappers.logger('Filtering df output.', level = 'DEBUG')
def _filter_df(output):
	disk_usages = {}

	for line in output[1:]:
		line = sub("\n", "", line)
		line = sub(" +", ",", line)
		line = split(",", line)

		if '/dev' in line[0]:
			disk_usages[line[0]] = {
				'size': line[1],
				'used': line[2],
				'free': line[3],
				'percent': line[4],
				'mount': line[5]
			}

	return disk_usages


@wrappers.logger('Loading disk usage.')
@wrappers.injector
def _load_disk_usage(log, config):
	off_disk_usages = {}

	# Load mounted disk usage.
	raw_mounted_disk_usages = console('df -h --sync').splitlines()
	mounted_disk_usages = _filter_df(raw_mounted_disk_usages)

	try:
		# Load unmounted / off disk usage from file.
		with open(config.disk_usage_path) as file_data:
			off_disk_usages = file_data.readlines()

		off_disk_usages = _filter_df(off_disk_usages)

		# Remove any duplicates.
		for key in mounted_disk_usages:
			if off_disk_usages.get(key):
				del off_disk_usages[key]
	except FileNotFoundError:
		log.warning('{0} does not exist, creating file with current disk usage.'.format(config.disk_usage_path))
		with open(config.disk_usage_path, 'w+') as file_data:
			file_data.write(raw_mounted_disk_usages[0])

			for line in raw_mounted_disk_usages[1:]:
				if '/dev/sd' in line:
					file_data.write(line)

	return mounted_disk_usages, off_disk_usages


@wrappers.logger('Checking mounted drives.')
def _mounted_drives(partitions, devices, mounted_disk_usages):
	for device in devices:
		if device['mountpoint'] is not None:
			usage = mounted_disk_usages.get(device['name'])

			if usage:
				partitions.append({
					'status': 'mounted',
					'label': device['label'],
					'device': device['name'],
					'size': usage['size'],
					'used': usage['used'],
					'free': usage['free'],
					'percent': usage['percent'],
					'type': device['fstype'],
					'mount': device['mountpoint'],
					'smart': ''
				})
			else:
				# Device name could differ from df command.
				for mounted_disk in mounted_disk_usages:
					mounted_disk = mounted_disk_usages.get(mounted_disk)

					if device['mountpoint'] == mounted_disk['mount']:
						partitions.append({
							'status': 'mounted',
							'label': device['label'],
							'device': device['name'],
							'size': mounted_disk['size'],
							'used': mounted_disk['used'],
							'free': mounted_disk['free'],
							'percent': mounted_disk['percent'],
							'type': device['fstype'],
							'mount': device['mountpoint'],
							'smart': ''
						})


@wrappers.logger('Checking unmounted drives.')
def _unmounted_drives(partitions, devices, off_disk_usages):
	for device in devices:
		if device['mountpoint'] is None:
			usage = off_disk_usages.get(device['name'])

			if usage:
				partitions.append({
					'status': 'unmounted',
					'label': device['label'],
					'device': device['name'],
					'size': usage['size'],
					'used': usage['used'],
					'free': usage['free'],
					'percent': usage['percent'],
					'type': device['fstype'],
					'mount': '',
					'smart': ''
				})

				del off_disk_usages[device['name']]
			else:
				partitions.append({
					'status': 'unmounted',
					'label': device['label'],
					'device': device['name'],
					'size': device['size'],
					'used': '',
					'free': '',
					'percent': '',
					'type': device['fstype'],
					'mount': '',
					'smart': ''
				})


# BUG: sdd1 and sdb1 are swapped in the dfn_disk_usage file (mount points), possibly causing them to not be listed.
@wrappers.logger('Checking off drives.')
def _off_drives(partitions, off_disk_usages):
	for key in off_disk_usages:
		device = off_disk_usages.get(key)

		partitions.append({
			'status': 'off',
			'label': '',
			'device': key,
			'size': device['size'],
			'used': device['used'],
			'free': device['free'],
			'percent': device['percent'],
			'type': '',
			'mount': '',
			'smart': ''
		})


@wrappers.logger('Loading disk partitions and usage.')
def disk_partitions():
	partitions = []
	devices = _list_fs_devices()
	mounted_disk_usages, off_disk_usages = _load_disk_usage()

	_mounted_drives(partitions, devices, mounted_disk_usages)
	_unmounted_drives(partitions, devices, off_disk_usages)
	_off_drives(partitions, off_disk_usages)

	return partitions


@wrappers.jwt
@wrappers.endpoint
@wrappers.stats
@wrappers.injector
def get(handler):
	handler.add({ 'partitions': disk_partitions() })

