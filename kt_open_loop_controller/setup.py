from setuptools import setup
import os
from glob import glob

package_name = "kt_open_loop_controller"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="dev",
    maintainer_email="dev@todo.todo",
    description="KT open-loop control bridge with HTTP API and radar safety",
    license="TODO",
    entry_points={
        "console_scripts": [
            "kt_control_bridge = kt_open_loop_controller.kt_control_bridge:main",
        ],
    },
)
