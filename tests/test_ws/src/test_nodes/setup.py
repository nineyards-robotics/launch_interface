import os
from glob import glob

from setuptools import setup

package_name = 'test_nodes'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), [
            f for f in glob('launch/*') if os.path.isfile(f)
        ]),
        (os.path.join('share', package_name, 'params'), [
            f for f in glob('params/*') if os.path.isfile(f)
        ]),
    ],
    install_requires=['setuptools'],
    entry_points={
        'console_scripts': [
            'node_a = test_nodes.node_a:main',
            'node_b = test_nodes.node_b:main',
        ],
    },
)
