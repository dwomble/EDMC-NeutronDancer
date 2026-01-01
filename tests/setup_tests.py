#!/usr/bin/env python3
"""
Setup script for the Neutron Dancer test harness.
Creates a virtual environment and installs dependencies.
"""

import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run a shell command and report status."""
    print(f"\n{description}...")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"Warning: Command failed with return code {result.returncode}")
        return False
    return True

def main():
    plugin_dir = Path(__file__).parent
    venv_dir = plugin_dir / ".venv"
    
    print("=" * 60)
    print("Neutron Dancer Test Harness Setup")
    print("=" * 60)
    
    # Check if venv already exists
    if venv_dir.exists():
        print(f"\nVirtual environment already exists at {venv_dir}")
        response = input("Recreate? (y/n): ").strip().lower()
        if response == 'y':
            import shutil
            shutil.rmtree(venv_dir)
        else:
            print("Using existing virtual environment")
            return
    
    # Create virtual environment
    if not run_command(
        f"python3 -m venv {venv_dir}",
        "Creating virtual environment"
    ):
        print("Failed to create virtual environment")
        return False
    
    # Get the python path in venv
    python_path = venv_dir / "bin" / "python"
    pip_path = venv_dir / "bin" / "pip"
    
    # Upgrade pip
    run_command(
        f"{pip_path} install --upgrade pip",
        "Upgrading pip"
    )
    
    # Install requirements
    requirements_file = plugin_dir / "requirements.txt"
    if requirements_file.exists():
        run_command(
            f"{pip_path} install -r {requirements_file}",
            "Installing requirements"
        )
    
    # Install pytest if developing
    run_command(
        f"{pip_path} install pytest pytest-cov",
        "Installing test dependencies"
    )
    
    print("\n" + "=" * 60)
    print("Setup complete!")
    print("=" * 60)
    print(f"\nTo use the virtual environment:")
    print(f"  source {venv_dir}/bin/activate")
    print(f"\nTo run tests:")
    print(f"  source {venv_dir}/bin/activate")
    print(f"  pytest test_plugin.py -v")
    print(f"\nTo run examples:")
    print(f"  source {venv_dir}/bin/activate")
    print(f"  python examples.py")

if __name__ == '__main__':
    main()
