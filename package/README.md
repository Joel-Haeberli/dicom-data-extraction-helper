# DICOM Data Extraction Helper - Packaging

This directory contains build scripts for packaging the application as standalone executables.

## Prerequisites

- Python 3.8+
- pip

## Building

### Windows

1. Open Command Prompt as Administrator
2. Run the build script:
   ```cmd
   build_windows.bat
   ```
3. The executable will be created at `dist/DICOM-Data-Extraction-Helper.exe`

### Linux

1. Make the build script executable:
   ```bash
   chmod +x build_linux.sh
   ```
2. Run the build script:
   ```bash
   ./build_linux.sh
   ```
3. The executable will be created at `dist/DICOM-Data-Extraction-Helper`

## Output

After building, you'll find:
- `dist/` - Contains the standalone executable
- `build/` - Temporary build files (can be deleted)
- `venv/` - Virtual environment (can be deleted after build)

## Running the Executable

### Windows
```cmd
dist\DICOM-Data-Extraction-Helper.exe
```

### Linux
```bash
./dist/DICOM-Data-Extraction-Helper
```

## Notes

- The executable is self-contained and does not require Python to be installed on the target machine
- On first run, the executable may take a few seconds to start (it's unpacking itself)
- If you get antivirus warnings on Windows, you may need to add an exception or sign the executable
- For production use, consider code signing the executable

## Custom Icon (Optional)

To use a custom icon:
1. Create a `.ico` file (Windows) or `.png` file (Linux)
2. Place it in the `package/` directory as `app_icon.ico` (Windows) or `app_icon.png` (Linux)
3. The build scripts will automatically pick it up

## Troubleshooting

### Missing Dependencies
If the executable fails to run, check that all Python packages in `requirements.txt` are installed.

### Qt Platform Plugin Issues
If you see errors about Qt platform plugins, you may need to add:
```
--add-data "PySide6/Qt/plugins:PySide6/Qt/plugins"
```
to the PyInstaller command.

### Large Executable Size
The onefile executable will be large (50-100MB) because it bundles Python, Qt, and all dependencies. This is normal.

## Alternative: Using Nuitka

For potentially smaller and faster executables, you can use Nuitka:

### Install Nuitka
```bash
pip install nuitka
```

### Build with Nuitka (Linux)
```bash
nuitka --onefile --windows-disable-console --output-dir=dist gui/main.py
```

### Build with Nuitka (Windows)
```cmd
python -m nuitka --onefile --windows-disable-console --output-dir=dist gui\main.py
```
