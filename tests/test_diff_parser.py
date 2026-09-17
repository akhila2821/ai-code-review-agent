"""
Tests for the unified diff parser.
"""

import pytest
from app.services.diff_parser import diff_to_text, parse_diff

SAMPLE_DIFF = """\
diff --git a/app/utils.py b/app/utils.py
index 1234567..abcdefg 100644
--- a/app/utils.py
+++ b/app/utils.py
@@ -10,6 +10,10 @@ def existing_function():
     pass
 
+def new_function(x: int) -> int:
+    \"\"\"Add one to x.\"\"\"
+    return x + 1
+
 def another_function():
     pass
diff --git a/tests/test_utils.py b/tests/test_utils.py
new file mode 100644
--- /dev/null
+++ b/tests/test_utils.py
@@ -0,0 +1,5 @@
+import pytest
+from app.utils import new_function
+
+def test_new_function():
+    assert new_function(1) == 2
"""


def test_parse_diff_returns_file_diffs():
    file_diffs = parse_diff(SAMPLE_DIFF)
    assert len(file_diffs) == 2


def test_parse_diff_filenames():
    file_diffs = parse_diff(SAMPLE_DIFF)
    filenames = [fd.filename for fd in file_diffs]
    assert "app/utils.py" in filenames
    assert "tests/test_utils.py" in filenames


def test_parse_diff_statuses():
    file_diffs = parse_diff(SAMPLE_DIFF)
    statuses = {fd.filename: fd.status for fd in file_diffs}
    assert statuses["app/utils.py"] == "modified"
    assert statuses["tests/test_utils.py"] == "added"


def test_parse_diff_hunks():
    file_diffs = parse_diff(SAMPLE_DIFF)
    utils_diff = next(fd for fd in file_diffs if fd.filename == "app/utils.py")
    assert len(utils_diff.hunks) == 1
    hunk = utils_diff.hunks[0]
    assert hunk.old_start == 10
    assert hunk.new_start == 10


def test_parse_empty_diff():
    assert parse_diff("") == []
    assert parse_diff("   ") == []


def test_diff_to_text_truncation():
    # Create a large fake diff
    big_diff_line = "+" + "x" * 1024  # 1 KB per line
    big_file = (
        "diff --git a/big.py b/big.py\n"
        "--- a/big.py\n"
        "+++ b/big.py\n"
        "@@ -1,0 +1,1000 @@\n"
        + "\n".join([big_diff_line] * 600)  # ~600 KB
    )
    file_diffs = parse_diff(big_file)
    result = diff_to_text(file_diffs, max_kb=100)
    assert "truncated" in result.lower() or len(result) <= 102_400 + 500


def test_diff_to_text_includes_filenames():
    file_diffs = parse_diff(SAMPLE_DIFF)
    text = diff_to_text(file_diffs)
    assert "app/utils.py" in text
    assert "tests/test_utils.py" in text
