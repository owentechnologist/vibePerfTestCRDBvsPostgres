#!/bin/bash
# Setup script for PostgreSQL Performance Benchmark project
# Creates virtual environment and installs all dependencies

set -e  # Exit on error

echo "=================================================================="
echo "PostgreSQL Performance Benchmark - Environment Setup"
echo "=================================================================="

# Check Python version
echo ""
echo "[1/5] Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

echo "  Found Python $PYTHON_VERSION"

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    echo "  ❌ Python 3.10 or higher is required"
    echo "  Please install Python 3.10+ and try again"
    exit 1
fi

echo "  ✅ Python version compatible"

# Create virtual environment
echo ""
echo "[2/5] Creating virtual environment..."
if [ -d "venv" ]; then
    echo "  ⚠️  Virtual environment already exists at ./venv"
    read -p "  Delete and recreate? [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "  Removing existing venv..."
        rm -rf venv
    else
        echo "  Using existing venv"
    fi
fi

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  ✅ Virtual environment created at ./venv"
else
    echo "  ✅ Using existing virtual environment"
fi

# Activate virtual environment
echo ""
echo "[3/5] Activating virtual environment..."
source venv/bin/activate
echo "  ✅ Virtual environment activated"

# Upgrade pip
echo ""
echo "[4/5] Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo "  ✅ pip upgraded to latest version"

# Install dependencies
echo ""
echo "[5/5] Installing dependencies from requirements.txt..."
echo "  This may take a few minutes..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "  ✅ All dependencies installed successfully"
else
    echo "  ❌ Failed to install dependencies"
    exit 1
fi

# Verify installation
echo ""
echo "=================================================================="
echo "Verifying Installation"
echo "=================================================================="

python3 << 'EOF'
import sys

packages = [
    ('asyncpg', 'asyncpg'),
    ('psycopg2', 'psycopg2-binary'),
    ('numpy', 'numpy'),
    ('rich', 'rich'),
    ('jinja2', 'jinja2'),
    ('psutil', 'psutil'),
    ('yaml', 'pyyaml'),
]

all_ok = True
for import_name, display_name in packages:
    try:
        module = __import__(import_name)
        version = getattr(module, '__version__', 'unknown')
        print(f"  ✅ {display_name:15} version {version}")
    except ImportError:
        print(f"  ❌ {display_name:15} NOT INSTALLED")
        all_ok = False

if all_ok:
    print("\n✅ All packages installed successfully!")
    sys.exit(0)
else:
    print("\n❌ Some packages failed to install")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Installation verification failed"
    exit 1
fi

# Success message
echo ""
echo "=================================================================="
echo "✅ Setup Complete!"
echo "=================================================================="
echo ""
echo "To activate the virtual environment in the future, run:"
echo "  source venv/bin/activate"
echo ""
echo "To deactivate when done:"
echo "  deactivate"
echo ""
echo "Next steps:"
echo "  1. Authenticate with CockroachDB Cloud:"
echo "     ccloud auth login"
echo ""
echo "  2. Deploy CockroachDB cluster:"
echo "     python deploy_crdb.py --config cluster_config.yaml"
echo ""
echo "  3. Run benchmark:"
echo "     python benchmark.py --crdb \$(cat crdb_connection.txt) --pg <azure-pg-conn>"
echo ""
echo "=================================================================="
