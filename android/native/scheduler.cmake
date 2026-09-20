# This target links actual decompiled scheduling/IRQ functions. It is NOT the game.
option(SM64DS_TEST_UPSTREAM_SCHEDULER "Build the original 32-bit scheduler probe" OFF)
if(SM64DS_TEST_UPSTREAM_SCHEDULER)
    if(NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
        message(FATAL_ERROR "Scheduler probe requires 32-bit pointers; ARM64 game layouts are not ported")
    endif()
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    get_filename_component(REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
    set(SCHED_ADAPTER "${CMAKE_CURRENT_BINARY_DIR}/boot2_thread_portable.cpp")
    set(SCHED_RT "${CMAKE_CURRENT_BINARY_DIR}/scheduler_rt.cpp")
    add_custom_command(OUTPUT "${SCHED_ADAPTER}"
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/adapt_scheduler.py"
            "${REPO_ROOT}/port/hal/boot2_thread.cpp" "${SCHED_ADAPTER}"
        DEPENDS "${REPO_ROOT}/port/hal/boot2_thread.cpp" tools/adapt_scheduler.py VERBATIM)
    add_custom_command(OUTPUT "${SCHED_RT}"
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/adapt_runtime.py"
            "${REPO_ROOT}/port/ntr/rt.cpp" "${SCHED_RT}"
        DEPENDS "${REPO_ROOT}/port/ntr/rt.cpp" tools/adapt_runtime.py VERBATIM)
    add_library(sm64ds_scheduler_support STATIC "${SCHED_ADAPTER}")
    target_include_directories(sm64ds_scheduler_support PRIVATE
        "${REPO_ROOT}/port/ntr/include" "${REPO_ROOT}/port/hal")
    target_compile_definitions(sm64ds_scheduler_support PRIVATE SM64DS_NATIVE_FIBERS=1)
    target_compile_options(sm64ds_scheduler_support PRIVATE -fno-strict-aliasing)
    target_link_libraries(sm64ds_scheduler_support PUBLIC sm64ds_fibers)
    # Test includes the same generated scheduler to inspect invariants without
    # adding test-only entry points to the production module.
    set_source_files_properties(tests/scheduler_worker_test.cpp PROPERTIES OBJECT_DEPENDS "${SCHED_ADAPTER}")
    set(SCHED_ROM_SOURCES
        src/OS_SleepThread.c src/OS_WakeupThread.c src/func_02057f54.c
        src/func_0205801c.c src/func_02057e34.c src/func_0201a4d0.c
        src/func_0201a4bc.c src/_ZN3IRQ13VBlankHandlerEv.c)
    list(TRANSFORM SCHED_ROM_SOURCES PREPEND "${REPO_ROOT}/")
    add_executable(sm64ds_scheduler_tests tests/scheduler_worker_test.cpp "${SCHED_RT}" ${SCHED_ROM_SOURCES})
    target_include_directories(sm64ds_scheduler_tests PRIVATE "${CMAKE_CURRENT_BINARY_DIR}"
        "${REPO_ROOT}/include" "${REPO_ROOT}/port" "${REPO_ROOT}/port/hal"
        "${REPO_ROOT}/port/ntr/include")
    target_compile_definitions(sm64ds_scheduler_tests PRIVATE SM64DS_NATIVE_FIBERS=1 SM64DS_PLATFORM_PC=1)
    target_compile_options(sm64ds_scheduler_tests PRIVATE -fno-strict-aliasing)
    target_link_libraries(sm64ds_scheduler_tests PRIVATE sm64ds_fibers)
    add_test(NAME original_scheduler COMMAND sm64ds_scheduler_tests)
    set_tests_properties(original_scheduler PROPERTIES TIMEOUT 60)
endif()
