from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="lozzalingo",
    version="0.1.0",
    author="Laurence Stephan",
    author_email="your.email@example.com",
    description="A modular Flask admin dashboard framework with analytics, authentication, and more",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/lozzalingo",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Framework :: Flask",
    ],
    python_requires=">=3.8",
    install_requires=[
        "Flask>=3.0.0",
        "Flask-SQLAlchemy>=3.0.0",
        "Flask-CORS>=4.0.0",
        "python-dotenv>=1.0.0",
        "requests>=2.28.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-flask>=1.2",
            "black>=22.0",
            "flake8>=5.0",
        ],
    },
    include_package_data=True,
    package_data={
        "lozzalingo": [
            "modules/*/templates/**/*.html",
            "modules/*/static/**/*.css",
            "modules/*/static/**/*.js",
            "modules/*/static/**/*.png",
            "modules/*/static/**/*.jpg",
            "modules/*/static/**/*.svg",
        ],
    },
    zip_safe=False,
)
