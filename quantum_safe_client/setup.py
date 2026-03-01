"""
QuantumSafe Client SDK - Setup configuration.
"""

from setuptools import find_packages, setup

with open("README.md", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="quantum-safe-client",
    version="1.0.0",
    author="QuantumSafe Team",
    author_email="support@quantumsafe.io",
    description="Python SDK for the QuantumSafe Quantum Optimization Platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/quantumsafe/quantum-safe-client",
    project_urls={
        "Bug Tracker": "https://github.com/quantumsafe/quantum-safe-client/issues",
        "Documentation": "https://docs.quantumsafe.io/sdk/python",
        "Source": "https://github.com/quantumsafe/quantum-safe-client",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Typing :: Typed",
    ],
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.9",
    install_requires=[
        "httpx>=0.24.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
            "ruff>=0.1.0",
        ],
    },
    keywords=[
        "quantum",
        "quantum-computing",
        "optimization",
        "qaoa",
        "vqe",
        "quantum-annealing",
        "post-quantum-cryptography",
        "sdk",
        "api-client",
    ],
)
