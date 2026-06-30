"""Tests for spurious-unused-imports challenge.

Illustrates unused import errors across multiple languages.
"""
import textwrap

import pytest

class TestSpuriousUnusedImports:
    """Test scenarios illustrating unused import challenges."""

    def test_python_unused_stdlib_imports(self, tmp_path):
        """Python code with unused standard library imports."""
        (tmp_path / 'main.py').write_text(textwrap.dedent("""\
            import os
            import sys
            import json
            import datetime
            import random
            import re
            
            def main():
                print("Hello, World!")
        """))
        
        content = (tmp_path / 'main.py').read_text()
        imports = ['import os', 'import sys', 'import json', 'import datetime', 'import random', 'import re']
        for imp in imports:
            assert imp in content
        # Many imports but only print is used
        assert 'print(' in content
        # All the imports except builtins are unused

    def test_python_unused_thirdparty_imports(self, tmp_path):
        """Python code with unused third-party imports."""
        (tmp_path / 'main.py').write_text(textwrap.dedent("""\
            import requests
            import numpy as np
            import pandas as pd
            import matplotlib.pyplot as plt
            import tensorflow as tf
            
            def calculate():
                return 42
        """))
        
        content = (tmp_path / 'main.py').read_text()
        unused_imports = ['import requests', 'numpy', 'pandas', 'matplotlib', 'tensorflow']
        for imp in unused_imports:
            assert imp in content
        # Many heavy imports but none are used in the simple calculate function

    def test_csharp_unused_using_directives(self, tmp_path):
        """C# code with unused using directives."""
        (tmp_path / 'Program.cs').write_text(textwrap.dedent("""\
            using System;
            using System.Collections.Generic;
            using System.Linq;
            using System.Text;
            using System.IO;
            using System.Net;
            using System.Threading.Tasks;
            
            namespace MyApp
            {
                class Program
                {
                    static void Main()
                    {
                        Console.WriteLine("Hello");
                    }
                }
            }
        """))
        
        content = (tmp_path / 'Program.cs').read_text()
        unused_usings = ['using System.Collections.Generic', 'using System.Linq', 
                       'using System.Text', 'using System.IO', 'using System.Net', 
                       'using System.Threading.Tasks']
        for using in unused_usings:
            assert using in content
        # Many using directives but only System is used for Console

    def test_go_unused_imports(self, tmp_path):
        """Go code with unused imports."""
        (tmp_path / 'main.go').write_text(textwrap.dedent("""\
            package main
            
            import (
                "fmt"
                "os"
                "strings"
                "time"
                "net/http"
                "encoding/json"
            )
            
            func main() {
                fmt.Println("Hello")
            }
        """))
        
        content = (tmp_path / 'main.go').read_text()
        unused_imports = ['"os"', '"strings"', '"time"', '"net/http"', '"encoding/json"']
        for imp in unused_imports:
            assert imp in content
        # Many imports but only fmt is used