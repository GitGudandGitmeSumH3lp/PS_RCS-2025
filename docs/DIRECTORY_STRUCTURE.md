# Project Directory Structure

├── backend
├── Camera-visualizer
│   └── templates
│       ├── css
│       │   └── styles.css
│       └── js
│           └── main.js
├── config
│   ├── requirements.txt
│   ├── requirements_lidar.txt
│   ├── requirements_ocr.txt
│   └── settings.json
├── couriers
│   └── flash-express.js
├── data
│   ├── captures
│   ├── database.db
│   ├── receipts.db
│   ├── robot.db
│   └── test.db
├── debug_alignment
│   ├── 20260215_192909_647681_aligned.jpg
│   ├── 20260215_192909_647681_original.jpg
│   ├── 20260215_194224_813946_aligned.jpg
│   ├── 20260215_194224_813946_original.jpg
│   ├── 20260215_194245_853811_aligned.jpg
│   ├── 20260215_194245_853811_original.jpg
│   ├── 20260215_195026_741537_aligned.jpg
│   ├── 20260215_195026_741537_original.jpg
│   ├── 20260215_200219_600044_aligned.jpg
│   ├── 20260215_200219_600044_original.jpg
│   ├── 20260215_200816_093512_aligned.jpg
│   └── 20260215_200816_093512_original.jpg
├── debug_zones
│   ├── zone1_processed.jpg
│   ├── zone1_raw.jpg
│   ├── zone3_processed.jpg
│   ├── zone3_raw.jpg
│   ├── zone5_processed.jpg
│   └── zone5_raw.jpg
├── docs
│   ├── architecture
│   │   ├── api_server_v1.py
│   │   ├── api_server_v2.py
│   │   ├── app_alternate.py
│   │   ├── dashboard_copy.html
│   │   ├── frontend_config.py
│   │   ├── index2.html
│   │   ├── indexbase.html
│   │   ├── index_copy.html
│   │   ├── lidar_testserver.py
│   │   ├── test.html
│   │   └── test_1.html
│   ├── contracts
│   │   ├── archive
│   │   │   ├── dashboard_core_js.md
│   │   │   ├── service_dashboard.html.md
│   │   │   └── service_theme_css.md
│   │   ├── backend_modularization.md
│   │   ├── camera_hal_v1.md
│   │   ├── config.md
│   │   ├── csi_camera_provider.md
│   │   ├── csi_provider_yuv420_fix.md
│   │   ├── database_core.md
│   │   ├── db_sync_refactor.md
│   │   ├── flash_express_zonal_implementation.md
│   │   ├── flash_express_zonal_ocr.md
│   │   ├── flash_express_zonal_visual_failure_analysis.md
│   │   ├── frontend_interface.md
│   │   ├── hardware_interface.md
│   │   ├── motor_driver_integration.md
│   │   ├── multi_courier_parcel_gen.md
│   │   ├── multi_courier_work_order.md
│   │   ├── ocr_failure_analysis.md
│   │   ├── ocr_flash_express.md
│   │   ├── ocr_performance_test.md
│   │   ├── ocr_results_display_bug_contract.md
│   │   ├── ocr_results_display_bug_work_order.md
│   │   ├── ocr_scanner_enhancement.md
│   │   ├── service_dashboard.md
│   │   ├── service_manager.md
│   │   ├── state_manager.md
│   │   ├── ui_modernization.md
│   │   ├── ui_overhaul.md
│   │   ├── ui_refinement.md
│   │   ├── vision_manager_optimization.md
│   │   ├── vision_manager_stream_fix_contract.md
│   │   ├── vision_ocr_system.md
│   │   ├── vision_ocr_work_order.md
│   │   ├── vision_panel_error_state_fix_contract.md
│   │   ├── vision_panel_error_state_fix_contract_work_order.md
│   │   ├── work_order_camera_hal.md
│   │   └── work_order_vision_stream_fix.md
│   ├── research
│   │   └── ocr_accuracy_improvement_plan.md
│   ├── sessions
│   │   └── session_notes_2026-02-11.md
│   ├── state_archives
│   │   ├── _STATE copy.MD
│   │   └── _STATE_archive.md
│   ├── API_MAP.MD
│   ├── API_MAP_LITE.bak
│   ├── API_MAP_LITE.md
│   ├── API_MAP_LITE_bak.md
│   ├── DIRECTORY_STRUCTURE.md
│   ├── hotfix_log.md
│   ├── memory_snippet.md
│   ├── project_memory.md
│   ├── system_constraints.md
│   └── system_style.md
├── frontend
│   ├── static
│   │   ├── css
│   │   │   ├── enterprise-theme.css
│   │   │   ├── neural-theme.css
│   │   │   ├── ocr-panel.css
│   │   │   ├── service_theme.css
│   │   │   └── styles.css
│   │   ├── images
│   │   ├── js
│   │   │   ├── chart_config.js
│   │   │   ├── dashboard-core.js
│   │   │   ├── dashboard-core.js copy.bak
│   │   │   ├── datatable.js
│   │   │   ├── main.js
│   │   │   ├── neural-core.js
│   │   │   ├── ocr-panel.js
│   │   │   └── script.js
│   │   └── models
│   └── templates
│       ├── service_dashboard.html
│       └── test
├── Huskylens-visualizer
├── Lidar-visualizer
│   └── templates
│       ├── css
│       │   └── styles.css
│       └── js
│           └── main.js
├── OCR_sim
│   ├── images
│   │   ├── train_01.jpg
│   │   ├── train_02.jpg
│   │   ├── train_03.jpg
│   │   ├── train_04.jpg
│   │   ├── train_05.jpg
│   │   ├── train_06.jpg
│   │   └── train_07.jpg
│   └── ground_truth.json
├── scripts
│   └── clean_db_timestamps.py
├── specs
│   ├── 01_backend_refactor.md
│   ├── 02_frontend_refactor_v2.md
│   ├── 03_motor_controller.md
│   ├── 04.1_ui_modernization.md
│   ├── 04_UI_modernization.md
│   ├── 05_refactor_architecture_hal.md
│   ├── 06_vision_ocr_integration.md
│   ├── 07_vision_performance_optimization.md
│   ├── 08_vision_ui_integration.md
│   ├── 09_ui_overhaul_linear_spec.md
│   ├── 10_ui_refinement.md
│   ├── 11_vision_capture_bugfix_spec.md
│   ├── 12_ocr_results_display_bug_spec.md
│   ├── 13_camera_hal.md
│   ├── 14_csi_error_investigation.md
│   ├── 15_receipt_deskewing.md
│   └── 16_feature_multicourier_generator.md
├── src
│   ├── api
│   │   ├── server.py
│   │   ├── server.py.bak
│   │   └── server1.py.bak
│   ├── core
│   │   ├── config.py
│   │   ├── courier-registry.js
│   │   ├── ground-truth-exporter.js
│   │   ├── label-engine.js
│   │   ├── label-renderer.js
│   │   ├── state.py
│   │   ├── state.py.bak
│   │   └── state_manager.py
│   ├── database
│   │   ├── core.py
│   │   ├── db_manager.py
│   │   ├── models.py
│   │   ├── repository.py
│   │   ├── schema.sql
│   │   └── __init__.py
│   ├── drivers
│   │   ├── legacy_motor_adapter.py
│   │   └── mock_motor_driver.py
│   ├── firmware
│   │   └── arduino
│   │       └── motor_control.ino
│   ├── hardware
│   │   ├── camera
│   │   │   ├── base.py
│   │   │   ├── csi_provider.py
│   │   │   ├── discovery.py
│   │   │   ├── factory.py
│   │   │   ├── usb_provider.py
│   │   │   └── __init__.py
│   │   ├── huskylens
│   │   │   ├── client.py
│   │   │   ├── handler.py
│   │   │   ├── standalone_app.py
│   │   │   └── __init__.py
│   │   ├── lidar
│   │   │   ├── discovery.py
│   │   │   ├── handler.py
│   │   │   ├── handler_v2.py
│   │   │   └── __init__.py
│   │   ├── motor
│   │   │   ├── controller.py
│   │   │   └── __init__.py
│   │   ├── ocr
│   │   │   ├── optimized
│   │   │   │   ├── knowledge_base.py
│   │   │   │   ├── ocr.py
│   │   │   │   └── __init__.py
│   │   │   ├── handler.py
│   │   │   ├── knowledge_base.py
│   │   │   ├── ocr.py
│   │   │   ├── ocr_simple.py
│   │   │   ├── preprocessor.py
│   │   │   └── __init__.py
│   │   └── __init__.py
│   ├── interfaces
│   │   └── motor_interface.py
│   ├── services
│   │   ├── api
│   │   │   ├── server.py
│   │   │   └── __init__.py
│   │   ├── database
│   │   │   ├── core.py
│   │   │   └── __init__.py
│   │   ├── errors.txt
│   │   ├── hardware_manager.py
│   │   ├── hardware_manager.py.bak
│   │   ├── image_utils.py
│   │   ├── ocr_patterns.py
│   │   ├── ocr_processor.py
│   │   ├── ocr_service.py
│   │   ├── ocr_services.py
│   │   ├── receipt_database.py
│   │   ├── vision_manager.py
│   │   ├── vision_manager.py.bak
│   │   └── __init__.py
│   └── __init__.py
├── tests
│   ├── fixtures
│   │   └── images
│   │       └── receipts
│   │           ├── receipt.jpg
│   │           ├── receipt2.jpg
│   │           ├── receipt3.jpg
│   │           ├── receipt4.jpg
│   │           ├── receipt5.jpg
│   │           ├── receipt6.jpg
│   │           └── receipt7.jpg
│   ├── unit
│   │   ├── hardware
│   │   │   ├── test_huskylens.py
│   │   │   ├── test_lidar.py
│   │   │   ├── test_motor.py
│   │   │   ├── test_ocr.py
│   │   │   ├── test_ocr_advanced.py
│   │   │   ├── test_ocr_simple.py
│   │   │   └── __init__.py
│   │   ├── services
│   │   │   └── __init__.py
│   │   └── __init__.py
│   └── __init__.py
├── utils
│   ├── barcode-utils.js
│   ├── data-generators.js
│   └── dictionary-extractor.js
├── web
│   ├── client
│   │   ├── static
│   │   │   ├── css
│   │   │   │   └── styles.css
│   │   │   └── js
│   │   │       ├── datatable.js
│   │   │       ├── main.js
│   │   │       └── script.js
│   │   ├── templates
│   │   │   ├── control.html
│   │   │   ├── dashboard.html
│   │   │   └── index.html
│   │   ├── app.py
│   │   └── __init__.py
│   ├── visualizers
│   │   ├── camera
│   │   │   ├── templates
│   │   │   │   └── index.html
│   │   │   └── app.py
│   │   ├── lidar
│   │   │   ├── templates
│   │   │   │   ├── index.html
│   │   │   │   └── lidar_visualizer.html
│   │   │   └── app.py
│   │   ├── ocr
│   │   │   ├── templates
│   │   │   │   └── index.html
│   │   │   └── app.py
│   │   └── __init__.py
│   └── __init__.py
├── zip
│   ├── OCR-claude-fix
│   │   ├── COMPARISON.md
│   │   ├── FIX_DOCUMENTATION.md
│   │   ├── image_utils_fixed.py
│   │   ├── ocr_processor_fixed.py
│   │   └── test_ocr_fixes.py
│   └── files (1).zip
├── .env.example
├── camera_probe.py
├── checklist.md
├── chromium.log
├── errors.txt
├── ground_truth.json
├── main.py
├── migrate.SH
├── prioritiy_list.md
├── README.md
├── requirements.txt
├── system_constraints_frontend.md
├── test.jpg
├── test.py
├── test_concurrent_ocr.py
├── test_zonal_ocr.py
├── _STATE.MD
└── _STATE.MD.bak
