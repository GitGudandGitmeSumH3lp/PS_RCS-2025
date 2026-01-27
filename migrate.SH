#!/bin/bash

################################################################################
# LEGACY TO V3.5 MIGRATION SCRIPT
# Generated: 2026-01-20
# Purpose: Safely migrate robotics project to clean architecture
# WARNING: Review this script before running. Test on a copy first.
################################################################################

set -e  # Exit on any error
set -u  # Exit on undefined variable

echo "=================================="
echo "🚀 STARTING V3.5 MIGRATION"
echo "=================================="
echo ""

################################################################################
# PHASE 0: SAFETY BACKUP
################################################################################

echo "📦 PHASE 0: Creating safety backup..."
BACKUP_DIR="backup_legacy_$(date +%Y%m%d_%H%M%S)"

if [ -d "$BACKUP_DIR" ]; then
    echo "⚠️  Backup directory already exists: $BACKUP_DIR"
    echo "❌ Aborting to prevent overwriting existing backup"
    exit 1
fi

echo "   Creating backup folder: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

echo "   Copying entire project to backup..."
cp -r ./arduino "$BACKUP_DIR/" 2>/dev/null || true
cp -r ./backend "$BACKUP_DIR/" 2>/dev/null || true
cp -r ./Camera-visualizer "$BACKUP_DIR/" 2>/dev/null || true
cp -r ./frontend "$BACKUP_DIR/" 2>/dev/null || true
cp -r ./Huskylens-visualizer "$BACKUP_DIR/" 2>/dev/null || true
cp -r ./Lidar-visualizer "$BACKUP_DIR/" 2>/dev/null || true
cp -r ./OCR_sim "$BACKUP_DIR/" 2>/dev/null || true
cp -r ./tests "$BACKUP_DIR/" 2>/dev/null || true
cp *.txt "$BACKUP_DIR/" 2>/dev/null || true
cp *.md "$BACKUP_DIR/" 2>/dev/null || true
cp *.db "$BACKUP_DIR/" 2>/dev/null || true
cp requirements.txt "$BACKUP_DIR/" 2>/dev/null || true

echo "✅ Backup complete: $BACKUP_DIR"
echo ""

################################################################################
# PHASE 1: FOUNDATION SETUP
################################################################################

echo "🏗️  PHASE 1: Creating V3.5 directory structure..."

# Core source directories
echo "   Creating src/ hierarchy..."
mkdir -p src/hardware/huskylens
mkdir -p src/hardware/lidar
mkdir -p src/hardware/motor
mkdir -p src/hardware/ocr/optimized
mkdir -p src/hardware/camera
mkdir -p src/services/api/routes
mkdir -p src/services/database/models
mkdir -p src/firmware/arduino

# Web directories
echo "   Creating web/ hierarchy..."
mkdir -p web/client/static/css
mkdir -p web/client/static/js
mkdir -p web/client/static/images
mkdir -p web/client/static/models
mkdir -p web/client/templates
mkdir -p web/visualizers/camera/templates
mkdir -p web/visualizers/lidar/templates
mkdir -p web/visualizers/huskylens/templates
mkdir -p web/visualizers/shared

# Documentation
echo "   Creating docs/ hierarchy..."
mkdir -p docs/contracts
mkdir -p docs/guides
mkdir -p docs/architecture

# Tests
echo "   Creating tests/ hierarchy..."
mkdir -p tests/unit/hardware
mkdir -p tests/unit/services
mkdir -p tests/integration
mkdir -p tests/fixtures/images/receipts

# Config and data
echo "   Creating config/ and data/ directories..."
mkdir -p config
mkdir -p data/databases
mkdir -p data/logs

echo "✅ Directory structure created"
echo ""

################################################################################
# PHASE 2: CORE MIGRATION
################################################################################

echo "🔄 PHASE 2: Migrating files..."
echo ""

################################################################################
# 2.1: HARDWARE MODULES - HUSKYLENS
################################################################################

echo "📹 Migrating HuskyLens module..."

if [ -f "./Huskylens-visualizer/huskylib.py" ]; then
    echo "   Moving: huskylib.py → src/hardware/huskylens/client.py"
    mv ./Huskylens-visualizer/huskylib.py src/hardware/huskylens/client.py
fi

if [ -f "./Huskylens-visualizer/huskylens.py" ]; then
    echo "   Moving: huskylens.py → src/hardware/huskylens/standalone_app.py"
    mv ./Huskylens-visualizer/huskylens.py src/hardware/huskylens/standalone_app.py
fi

if [ -f "./backend/huskylens_handler.py" ]; then
    echo "   Moving: huskylens_handler.py → src/hardware/huskylens/handler.py"
    mv ./backend/huskylens_handler.py src/hardware/huskylens/handler.py
fi

if [ -f "./Huskylens-visualizer/huskylens_data.db" ]; then
    echo "   Moving: huskylens_data.db → data/databases/huskylens_data.db"
    mv ./Huskylens-visualizer/huskylens_data.db data/databases/huskylens_data.db
fi

# Create __init__.py for Python module
echo "   Creating: src/hardware/huskylens/__init__.py"
touch src/hardware/huskylens/__init__.py

echo ""

################################################################################
# 2.2: HARDWARE MODULES - LIDAR
################################################################################

echo "🎯 Migrating LiDAR module..."

if [ -f "./backend/lidar_handler.py" ]; then
    echo "   Moving: lidar_handler.py → src/hardware/lidar/handler.py"
    mv ./backend/lidar_handler.py src/hardware/lidar/handler.py
fi

if [ -f "./backend/lidar_handler2.py" ]; then
    echo "   Moving: lidar_handler2.py → src/hardware/lidar/handler_v2.py [REVIEW NEEDED]"
    mv ./backend/lidar_handler2.py src/hardware/lidar/handler_v2.py
fi

if [ -f "./Lidar-visualizer/findmylidar.py" ]; then
    echo "   Moving: findmylidar.py → src/hardware/lidar/discovery.py"
    mv ./Lidar-visualizer/findmylidar.py src/hardware/lidar/discovery.py
fi

# Create __init__.py
echo "   Creating: src/hardware/lidar/__init__.py"
touch src/hardware/lidar/__init__.py

echo ""

################################################################################
# 2.3: HARDWARE MODULES - MOTOR
################################################################################

echo "⚙️  Migrating Motor Controller module..."

if [ -f "./backend/motor_controller.py" ]; then
    echo "   Moving: motor_controller.py → src/hardware/motor/controller.py"
    mv ./backend/motor_controller.py src/hardware/motor/controller.py
fi

# Create __init__.py
echo "   Creating: src/hardware/motor/__init__.py"
touch src/hardware/motor/__init__.py

echo ""

################################################################################
# 2.4: FIRMWARE - ARDUINO
################################################################################

echo "🤖 Migrating Arduino firmware..."

if [ -f "./arduino/wheels/wheels.ino" ]; then
    echo "   Moving: wheels.ino → src/firmware/arduino/motor_control.ino"
    mv ./arduino/wheels/wheels.ino src/firmware/arduino/motor_control.ino
fi

echo ""

################################################################################
# 2.5: HARDWARE MODULES - OCR
################################################################################

echo "📄 Migrating OCR module..."

if [ -f "./backend/ocr_handler.py" ]; then
    echo "   Moving: ocr_handler.py → src/hardware/ocr/handler.py"
    mv ./backend/ocr_handler.py src/hardware/ocr/handler.py
fi

if [ -f "./OCR_sim/image_preprocessor.py" ]; then
    echo "   Moving: image_preprocessor.py → src/hardware/ocr/preprocessor.py"
    mv ./OCR_sim/image_preprocessor.py src/hardware/ocr/preprocessor.py
fi

if [ -f "./OCR_sim/knowledge_base.py" ]; then
    echo "   Moving: knowledge_base.py → src/hardware/ocr/knowledge_base.py"
    mv ./OCR_sim/knowledge_base.py src/hardware/ocr/knowledge_base.py
fi

if [ -f "./OCR_sim/knowledge_base_optimized.py" ]; then
    echo "   Moving: knowledge_base_optimized.py → src/hardware/ocr/optimized/knowledge_base.py"
    mv ./OCR_sim/knowledge_base_optimized.py src/hardware/ocr/optimized/knowledge_base.py
fi

if [ -f "./OCR_sim/ocr.py" ]; then
    echo "   Moving: ocr.py → src/hardware/ocr/ocr.py"
    mv ./OCR_sim/ocr.py src/hardware/ocr/ocr.py
fi

if [ -f "./OCR_sim/ocr_optimized.py" ]; then
    echo "   Moving: ocr_optimized.py → src/hardware/ocr/optimized/ocr.py"
    mv ./OCR_sim/ocr_optimized.py src/hardware/ocr/optimized/ocr.py
fi

if [ -f "./OCR_sim/ocr_simple.py" ]; then
    echo "   Moving: ocr_simple.py → src/hardware/ocr/ocr_simple.py"
    mv ./OCR_sim/ocr_simple.py src/hardware/ocr/ocr_simple.py
fi

if [ -f "./OCR_sim/scanned_data.db" ]; then
    echo "   Moving: scanned_data.db → data/databases/scanned_data.db"
    mv ./OCR_sim/scanned_data.db data/databases/scanned_data.db
fi

# Create __init__.py
echo "   Creating: src/hardware/ocr/__init__.py"
touch src/hardware/ocr/__init__.py
echo "   Creating: src/hardware/ocr/optimized/__init__.py"
touch src/hardware/ocr/optimized/__init__.py

echo ""

################################################################################
# 2.6: HARDWARE MODULES - CAMERA
################################################################################

echo "📷 Migrating Camera module..."

if [ -f "./Camera-visualizer/find_camera.py" ]; then
    echo "   Moving: find_camera.py → src/hardware/camera/discovery.py"
    mv ./Camera-visualizer/find_camera.py src/hardware/camera/discovery.py
fi

# Create __init__.py
echo "   Creating: src/hardware/camera/__init__.py"
touch src/hardware/camera/__init__.py

echo ""

################################################################################
# 2.7: BACKEND SERVICES - API
################################################################################

echo "🌐 Migrating API services..."

if [ -f "./backend/api_serverbase.py" ]; then
    echo "   Moving: api_serverbase.py → src/services/api/server.py [PRIMARY VERSION]"
    mv ./backend/api_serverbase.py src/services/api/server.py
fi

# Archive other API server versions for manual review
if [ -f "./backend/api_server.py" ]; then
    echo "   Archiving: api_server.py → docs/architecture/api_server_v1.py [REVIEW NEEDED]"
    mv ./backend/api_server.py docs/architecture/api_server_v1.py
fi

if [ -f "./backend/api_server2.py" ]; then
    echo "   Archiving: api_server2.py → docs/architecture/api_server_v2.py [REVIEW NEEDED]"
    mv ./backend/api_server2.py docs/architecture/api_server_v2.py
fi

if [ -f "./backend/app.py" ]; then
    echo "   Archiving: app.py → docs/architecture/app_alternate.py [REVIEW NEEDED]"
    mv ./backend/app.py docs/architecture/app_alternate.py
fi

if [ -f "./backend/lidar_testserver.py" ]; then
    echo "   Archiving: lidar_testserver.py → docs/architecture/lidar_testserver.py [REVIEW NEEDED]"
    mv ./backend/lidar_testserver.py docs/architecture/lidar_testserver.py
fi

# Create __init__.py
echo "   Creating: src/services/api/__init__.py"
touch src/services/api/__init__.py

echo ""

################################################################################
# 2.8: BACKEND SERVICES - DATABASE
################################################################################

echo "💾 Migrating Database services..."

if [ -f "./backend/database.py" ]; then
    echo "   Moving: database.py → src/services/database/core.py"
    mv ./backend/database.py src/services/database/core.py
fi

if [ -f "./backend/robot_data.db" ]; then
    echo "   Moving: robot_data.db → data/databases/robot_data.db"
    mv ./backend/robot_data.db data/databases/robot_data.db
fi

if [ -f "./robot_data.db" ]; then
    echo "   Moving: robot_data.db (root) → data/databases/robot_data_root.db [DUPLICATE]"
    mv ./robot_data.db data/databases/robot_data_root.db
fi

# Create __init__.py
echo "   Creating: src/services/database/__init__.py"
touch src/services/database/__init__.py

echo ""

################################################################################
# 2.9: FRONTEND - MAIN CLIENT
################################################################################

echo "🖥️  Migrating Frontend (Main Client)..."

if [ -f "./frontend/gui.py" ]; then
    echo "   Moving: gui.py → web/client/app.py"
    mv ./frontend/gui.py web/client/app.py
fi

# Move static files
if [ -d "./frontend/static/css" ]; then
    echo "   Moving: frontend/static/css/* → web/client/static/css/"
    cp -r ./frontend/static/css/* web/client/static/css/ 2>/dev/null || true
fi

if [ -d "./frontend/static/js" ]; then
    echo "   Moving: frontend/static/js/* → web/client/static/js/"
    cp -r ./frontend/static/js/* web/client/static/js/ 2>/dev/null || true
fi

if [ -d "./frontend/static/images" ]; then
    echo "   Moving: frontend/static/images/* → web/client/static/images/"
    cp -r ./frontend/static/images/* web/client/static/images/ 2>/dev/null || true
fi

if [ -d "./frontend/static/models" ]; then
    echo "   Moving: frontend/static/models/* → web/client/static/models/"
    cp -r ./frontend/static/models/* web/client/static/models/ 2>/dev/null || true
fi

# Move individual static files
if [ -f "./frontend/static/datatable.js" ]; then
    echo "   Moving: datatable.js → web/client/static/js/datatable.js"
    mv ./frontend/static/datatable.js web/client/static/js/datatable.js
fi

if [ -f "./frontend/static/main.js" ]; then
    echo "   Moving: main.js → web/client/static/js/main.js"
    mv ./frontend/static/main.js web/client/static/js/main.js
fi

if [ -f "./frontend/static/script.js" ]; then
    echo "   Moving: script.js → web/client/static/js/script.js"
    mv ./frontend/static/script.js web/client/static/js/script.js
fi

if [ -f "./frontend/static/styles.css" ]; then
    echo "   Moving: styles.css → web/client/static/css/styles.css"
    mv ./frontend/static/styles.css web/client/static/css/styles.css
fi

# Move templates
if [ -f "./frontend/templates/control.html" ]; then
    echo "   Moving: control.html → web/client/templates/control.html"
    mv ./frontend/templates/control.html web/client/templates/control.html
fi

if [ -f "./frontend/templates/dashboard.html" ]; then
    echo "   Moving: dashboard.html → web/client/templates/dashboard.html"
    mv ./frontend/templates/dashboard.html web/client/templates/dashboard.html
fi

if [ -f "./frontend/templates/index.html" ]; then
    echo "   Moving: index.html → web/client/templates/index.html"
    mv ./frontend/templates/index.html web/client/templates/index.html
fi

# Archive duplicate/test templates
if [ -f "./frontend/templates/dashboard copy.html" ]; then
    echo "   Archiving: dashboard copy.html → docs/architecture/dashboard_copy.html"
    mv "./frontend/templates/dashboard copy.html" docs/architecture/dashboard_copy.html
fi

if [ -f "./frontend/templates/index copy.html" ]; then
    echo "   Archiving: index copy.html → docs/architecture/index_copy.html"
    mv "./frontend/templates/index copy.html" docs/architecture/index_copy.html
fi

if [ -f "./frontend/templates/index2.html" ]; then
    echo "   Archiving: index2.html → docs/architecture/index2.html"
    mv ./frontend/templates/index2.html docs/architecture/index2.html
fi

if [ -f "./frontend/templates/indexbase.html" ]; then
    echo "   Archiving: indexbase.html → docs/architecture/indexbase.html"
    mv ./frontend/templates/indexbase.html docs/architecture/indexbase.html
fi

if [ -f "./frontend/templates/test.html" ]; then
    echo "   Archiving: test.html → docs/architecture/test.html"
    mv ./frontend/templates/test.html docs/architecture/test.html
fi

if [ -f "./frontend/templates/test(1).html" ]; then
    echo "   Archiving: test(1).html → docs/architecture/test_1.html"
    mv "./frontend/templates/test(1).html" docs/architecture/test_1.html
fi

# Note: config.py in templates is moved to docs for review (shouldn't be in templates)
if [ -f "./frontend/templates/config.py" ]; then
    echo "   Archiving: config.py (from templates) → docs/architecture/frontend_config.py [MISPLACED]"
    mv ./frontend/templates/config.py docs/architecture/frontend_config.py
fi

echo ""

################################################################################
# 2.10: WEB VISUALIZERS
################################################################################

echo "📊 Migrating Web Visualizers..."

# Camera Visualizer
if [ -f "./Camera-visualizer/app.py" ]; then
    echo "   Moving: Camera-visualizer/app.py → web/visualizers/camera/app.py"
    mv ./Camera-visualizer/app.py web/visualizers/camera/app.py
fi

if [ -f "./Camera-visualizer/templates/index.html" ]; then
    echo "   Moving: Camera-visualizer templates → web/visualizers/camera/templates/"
    mv ./Camera-visualizer/templates/index.html web/visualizers/camera/templates/index.html
fi

# LiDAR Visualizer
if [ -f "./Lidar-visualizer/app.py" ]; then
    echo "   Moving: Lidar-visualizer/app.py → web/visualizers/lidar/app.py"
    mv ./Lidar-visualizer/app.py web/visualizers/lidar/app.py
fi

if [ -f "./Lidar-visualizer/templates/index.html" ]; then
    echo "   Moving: Lidar-visualizer templates → web/visualizers/lidar/templates/"
    mv ./Lidar-visualizer/templates/index.html web/visualizers/lidar/templates/index.html
fi

if [ -f "./Lidar-visualizer/templates/lidar_visualizer.html" ]; then
    mv ./Lidar-visualizer/templates/lidar_visualizer.html web/visualizers/lidar/templates/lidar_visualizer.html
fi

# OCR Server (from OCR_sim)
if [ -f "./OCR_sim/server.py" ]; then
    echo "   Moving: OCR_sim/server.py → web/visualizers/ocr/app.py"
    mkdir -p web/visualizers/ocr/templates
    mv ./OCR_sim/server.py web/visualizers/ocr/app.py
fi

if [ -f "./OCR_sim/templates/index.html" ]; then
    echo "   Moving: OCR_sim templates → web/visualizers/ocr/templates/"
    mv ./OCR_sim/templates/index.html web/visualizers/ocr/templates/index.html
fi

echo ""

################################################################################
# 2.11: TESTS
################################################################################

echo "🧪 Migrating Tests..."

if [ -f "./tests/test_huskylens.py" ]; then
    echo "   Moving: test_huskylens.py → tests/unit/hardware/test_huskylens.py"
    mv ./tests/test_huskylens.py tests/unit/hardware/test_huskylens.py
fi

if [ -f "./tests/test_lidar.py" ]; then
    echo "   Moving: test_lidar.py → tests/unit/hardware/test_lidar.py"
    mv ./tests/test_lidar.py tests/unit/hardware/test_lidar.py
fi

if [ -f "./tests/test_motor.py" ]; then
    echo "   Moving: test_motor.py → tests/unit/hardware/test_motor.py"
    mv ./tests/test_motor.py tests/unit/hardware/test_motor.py
fi

if [ -f "./tests/test_ocr.py" ]; then
    echo "   Moving: test_ocr.py → tests/unit/hardware/test_ocr.py"
    mv ./tests/test_ocr.py tests/unit/hardware/test_ocr.py
fi

# Move OCR test files from OCR_sim
if [ -f "./OCR_sim/test_ocr.py" ]; then
    echo "   Moving: OCR_sim/test_ocr.py → tests/unit/hardware/test_ocr_advanced.py"
    mv ./OCR_sim/test_ocr.py tests/unit/hardware/test_ocr_advanced.py
fi

if [ -f "./OCR_sim/test_simple_ocr.py" ]; then
    echo "   Moving: OCR_sim/test_simple_ocr.py → tests/unit/hardware/test_ocr_simple.py"
    mv ./OCR_sim/test_simple_ocr.py tests/unit/hardware/test_ocr_simple.py
fi

# Move test images/fixtures
if [ -d "./OCR_sim/images" ]; then
    echo "   Moving: OCR_sim/images/* → tests/fixtures/images/receipts/"
    cp -r ./OCR_sim/images/* tests/fixtures/images/receipts/ 2>/dev/null || true
fi

if [ -f "./OCR_sim/receipt.jpg" ]; then
    echo "   Moving: OCR_sim/receipt.jpg → tests/fixtures/images/receipts/receipt.jpg"
    mv ./OCR_sim/receipt.jpg tests/fixtures/images/receipts/receipt.jpg
fi

echo ""

################################################################################
# 2.12: CONFIGURATION FILES
################################################################################

echo "⚙️  Migrating Configuration Files..."

if [ -f "./requirements.txt" ]; then
    echo "   Moving: requirements.txt → config/requirements.txt"
    mv ./requirements.txt config/requirements.txt
fi

if [ -f "./Lidar-visualizer/requirements.txt" ]; then
    echo "   Archiving: Lidar-visualizer/requirements.txt → config/requirements_lidar.txt"
    mv ./Lidar-visualizer/requirements.txt config/requirements_lidar.txt
fi

if [ -f "./OCR_sim/requirements.txt" ]; then
    echo "   Archiving: OCR_sim/requirements.txt → config/requirements_ocr.txt"
    mv ./OCR_sim/requirements.txt config/requirements_ocr.txt
fi

echo ""

################################################################################
# 2.13: DOCUMENTATION
################################################################################

echo "📚 Migrating Documentation..."

if [ -f "./README.md" ]; then
    echo "   Keeping: README.md in root (updating separately)"
    # Keep README.md in root, will be updated with new structure info
fi

if [ -f "./file_structure.txt" ]; then
    echo "   Archiving: file_structure.txt → docs/architecture/legacy_structure.txt"
    mv ./file_structure.txt docs/architecture/legacy_structure.txt
fi

if [ -f "./folder_list.txt" ]; then
    echo "   Archiving: folder_list.txt → docs/architecture/folder_list.txt"
    mv ./folder_list.txt docs/architecture/folder_list.txt
fi

if [ -f "./folder_stats.txt" ]; then
    echo "   Archiving: folder_stats.txt → docs/architecture/folder_stats.txt"
    mv ./folder_stats.txt docs/architecture/folder_stats.txt
fi

if [ -f "./migration_inventory.md" ]; then
    echo "   Moving: migration_inventory.md → docs/architecture/migration_inventory.md"
    mv ./migration_inventory.md docs/architecture/migration_inventory.md
fi

echo ""

################################################################################
# PHASE 3: GENERATE CONFIGURATION FILES
################################################################################

echo "📝 PHASE 3: Generating configuration files..."
echo ""

# Generate .env.example
echo "   Creating: .env.example"
cat > .env.example << 'EOF'
# Hardware Configuration
ARDUINO_PORT=/dev/ttyUSB0
HUSKYLENS_PORT=/dev/ttyUSB1
LIDAR_PORT=/dev/ttyUSB2
CAMERA_INDEX=0

# Database Configuration
DATABASE_PATH=./data/databases/robot.db
HUSKYLENS_DB_PATH=./data/databases/huskylens_data.db
OCR_DB_PATH=./data/databases/scanned_data.db

# API Configuration
API_HOST=0.0.0.0
API_PORT=5000
DEBUG_MODE=False

# Flask Configuration
FLASK_APP=web/client/app.py
FLASK_ENV=development
SECRET_KEY=change-this-to-random-secret-key

# Logging
LOG_LEVEL=INFO
LOG_PATH=./data/logs/robot.log

# Hardware Settings
MOTOR_SPEED_MAX=255
MOTOR_ACCELERATION=50
LIDAR_SCAN_RATE=10
HUSKYLENS_TIMEOUT=5
CAMERA_RESOLUTION_WIDTH=640
CAMERA_RESOLUTION_HEIGHT=480

# OCR Settings
OCR_CONFIDENCE_THRESHOLD=60
OCR_LANGUAGE=eng
EOF

# Generate .gitignore
echo "   Creating: .gitignore"
cat > .gitignore << 'EOF'
# Virtual Environments
venv/
*/venv/
env/
.venv/

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Databases
*.db
*.sqlite
*.sqlite3

# Environment
.env
.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
*.log
data/logs/

# Backups
backup_*/

# Build artifacts
build/
dist/
*.egg-info/
EOF

# Generate basic __init__.py files for all modules
echo "   Creating module __init__.py files..."
touch src/__init__.py
touch src/hardware/__init__.py
touch src/services/__init__.py
touch web/__init__.py
touch web/client/__init__.py
touch web/visualizers/__init__.py
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/unit/hardware/__init__.py
touch tests/unit/services/__init__.py

echo "✅ Configuration files created"
echo ""

################################################################################
# PHASE 4: CLEANUP (COMMENTED OUT - MANUAL REVIEW REQUIRED)
################################################################################

echo "🧹 PHASE 4: Cleanup (COMMENTED OUT)"
echo ""
echo "⚠️  The following cleanup commands are COMMENTED OUT for safety."
echo "   Review the migration results, then manually run these commands:"
echo ""
echo "   # Remove old directory structures (after verification)"
echo "   # rm -rf ./arduino"
echo "   # rm -rf ./backend"
echo "   # rm -rf ./Camera-visualizer"
echo "   # rm -rf ./frontend"
echo "   # rm -rf ./Huskylens-visualizer"
echo "   # rm -rf ./Lidar-visualizer"
echo "   # rm -rf ./OCR_sim"
echo "   # rm -rf ./tests  # (old location)"
echo "   # rm -rf ./venv   # Virtual environments should not be in git"
echo ""
echo "   # Remove pycache directories"
echo "   # find . -type d -name '__pycache__' -exec rm -rf {} +"
echo ""

################################################################################
# COMPLETION SUMMARY
################################################################################

echo "=================================="
echo "✅ MIGRATION COMPLETE"
echo "=================================="
echo ""
echo "📊 Summary:"
echo "   ✓ Created backup in: $BACKUP_DIR"
echo "   ✓ Created V3.5 directory structure"
echo "   ✓ Migrated hardware modules (huskylens, lidar, motor, ocr, camera)"
echo "   ✓ Migrated backend services (api, database)"
echo "   ✓ Migrated frontend client and visualizers"
echo "   ✓ Migrated tests and fixtures"
echo "   ✓ Organized configuration files"
echo "   ✓ Generated .env.example and .gitignore"
echo ""
echo "⚠️  NEXT STEPS:"
echo "   1. Review the new structure: ls -la src/ web/ docs/ tests/"
echo "   2. Copy .env.example to .env and configure your hardware ports"
echo "   3. Update import statements in Python files (backend.X → src.services.X)"
echo "   4. Test each module individually"
echo "   5. Review archived files in docs/architecture/ and merge if needed"
echo "   6. Run tests: python -m pytest tests/"
echo "   7. After verification, manually delete old directories (see cleanup section)"
echo ""
echo "📝 Files requiring manual review:"
echo "   - docs/architecture/api_server_v*.py (merge API server versions)"
echo "   - config/requirements_*.txt (consolidate dependencies)"
echo "   - data/databases/robot_data*.db (merge duplicate databases)"
echo "   - src/hardware/lidar/handler_v2.py (compare with handler.py)"
echo ""
echo "🔗 Backup location: $BACKUP_DIR"
echo ""

exit 0