# Native build of the engine tests. Used by CI (Linux, modern g++).
# The WebAssembly build is done by build.py with Emscripten.
cmake_minimum_required(VERSION 3.16)
project(rutalibre_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(rutalibre_core STATIC src/route.cpp)
target_include_directories(rutalibre_core PUBLIC include src)

add_executable(test_route tests/test_route.cpp)
target_link_libraries(test_route PRIVATE rutalibre_core)

enable_testing()
add_test(NAME test_route COMMAND test_route)
