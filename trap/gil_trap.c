#define PY_SSIZE_T_CLEAN
#include <Python.h>

static PyMethodDef methods[] = {
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    .m_name = "gil_trap",
    .m_doc = "Unmarked C extension. Importing it re-enables the GIL on 3.14t.",
    .m_size = -1,
    .m_methods = methods,
};

PyMODINIT_FUNC
PyInit_gil_trap(void)
{
    return PyModule_Create(&module);
}
