from setuptools import setup, find_packages

setup(
    name='mapai-xblock',
    version='0.1',
    description='XBlock con evaluación automática de mapas conceptuales usando Gemini AI',
    author='Andrés Pabón',
    license='MIT',
    packages=find_packages(),
    install_requires=[
        'XBlock',
        'requests'
    ],
    entry_points={
        'xblock.v1': [
            'mapai_xblock = mapai_xblock.mapai:MapAiXBlock',
        ],
    },
    package_data={
        "mapai_xblock": [
            "static/mapai/public/*.html",
            "static/mapai/public/*.js",
            "static/mapai/public/*.css",
        ],
    },
)

