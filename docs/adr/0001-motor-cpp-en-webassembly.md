# ADR 0001: Motor de rutas en C++ compilado a WebAssembly

Fecha: 2026-11-13 · Estado: aceptada

## Contexto

La vacante valora mucho la experiencia en C++. El cálculo de rutas es el único punto del producto donde el rendimiento y los algoritmos importan, así que es el lugar natural para C++. El servidor corre en Vercel, que ejecuta Python pero no compila C++ durante el despliegue.

## Decisión

Escribir el motor en C++17 sin dependencias ni memoria dinámica y compilarlo con Emscripten a un único `engine.wasm` independiente (`STANDALONE_WASM`, sin JavaScript de soporte). El mismo archivo:

- corre en el navegador para la vista previa instantánea;
- corre en el servidor dentro de FastAPI con `wasmtime`.

El binario compilado se versiona en el repositorio. El CI lo recompila desde el fuente y ejecuta los tests contra el binario nuevo.

## Consecuencias

- El C++ es visible para cualquier visitante: la comparación "sin optimizar contra optimizada" aparece sin esperar al servidor.
- Navegador y servidor dan exactamente el mismo resultado; un test lo verifica.
- No hace falta compilador en Vercel ni ruedas nativas de Python por plataforma.
- Límite fijo de 100 paradas por ruta, por los buffers estáticos.
- Quien cambie el motor debe recompilar y volver a versionar el `.wasm`.

## Alternativas descartadas

- **Extensión nativa con pybind11:** exige compilar por plataforma y no sirve en el navegador.
- **Ejecutable C++ invocado como subproceso:** frágil en funciones serverless y tampoco sirve en el navegador.
- **Reescribir el algoritmo en Python y JavaScript:** dos implementaciones que pueden divergir, y el C++ quedaría como decoración.
