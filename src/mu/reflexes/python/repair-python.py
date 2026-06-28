# repair-python.py

def handle_build_error(diagnostic):
    if 'No rule to make target' in diagnostic:
        return 'Check Makefile for correct dependencies and targets.'
    elif 'address already in use :PORT' in diagnostic:
        return 'Ensure the test does not start a blocking server subprocess.'
    else:
        return None

def handle_missing_import(diagnostic):
    if 'NameError: name' in diagnostic:
        return 'Add the missing import statement to the file.'
    else:
        return None
