"""Tests for simple utility functions in utils.py"""

import pytest

from dev_env.utils import hash_file, hash_config, format_size, parse_port_mapping


class TestHashFile:
  """Test hash_file function"""

  def test_hash_file_consistent(self, tmp_path):
    """Test that same file content produces same hash"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    hash1 = hash_file(test_file)
    hash2 = hash_file(test_file)

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 hex length

  def test_hash_file_different_content(self, tmp_path):
    """Test that different content produces different hashes"""
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"

    file1.write_text("content one")
    file2.write_text("content two")

    hash1 = hash_file(file1)
    hash2 = hash_file(file2)

    assert hash1 != hash2

  def test_hash_file_binary_content(self, tmp_path):
    """Test hashing binary files"""
    binary_file = tmp_path / "binary.bin"
    binary_file.write_bytes(b"\x00\x01\x02\x03\xff")

    hash_value = hash_file(binary_file)

    assert len(hash_value) == 64
    assert isinstance(hash_value, str)

  def test_hash_file_large_file(self, tmp_path):
    """Test hashing large files (tests chunked reading)"""
    large_file = tmp_path / "large.txt"

    # Create a file larger than 8192 bytes (chunk size)
    content = "A" * 10000
    large_file.write_text(content)

    hash_value = hash_file(large_file)

    assert len(hash_value) == 64


class TestHashConfig:
  """Test hash_config function"""

  def test_hash_config_consistent(self):
    """Test that same config produces same hash"""
    config = {"name": "test", "image": "python:3.13"}

    hash1 = hash_config(config)
    hash2 = hash_config(config)

    assert hash1 == hash2
    assert len(hash1) == 64

  def test_hash_config_order_independent(self):
    """Test that key order doesn't affect hash"""
    config1 = {"name": "test", "image": "python:3.13", "port": 8080}
    config2 = {"port": 8080, "image": "python:3.13", "name": "test"}

    hash1 = hash_config(config1)
    hash2 = hash_config(config2)

    assert hash1 == hash2

  def test_hash_config_different_values(self):
    """Test that different values produce different hashes"""
    config1 = {"name": "test1", "image": "python:3.13"}
    config2 = {"name": "test2", "image": "python:3.13"}

    hash1 = hash_config(config1)
    hash2 = hash_config(config2)

    assert hash1 != hash2

  def test_hash_config_nested_objects(self):
    """Test hashing nested configuration objects"""
    config = {
      "name": "test",
      "volumes": [{"source": "vol", "target": "/data"}],
      "env": {"VAR1": "value1", "VAR2": "value2"},
    }

    hash_value = hash_config(config)

    assert len(hash_value) == 64

    # Should be consistent
    assert hash_value == hash_config(config)

  def test_hash_config_empty_dict(self):
    """Test hashing empty configuration"""
    config = {}

    hash_value = hash_config(config)

    assert len(hash_value) == 64


class TestFormatSize:
  """Test format_size function"""

  def test_format_size_bytes(self):
    """Test formatting bytes"""
    assert format_size(0) == "0.0 B"
    assert format_size(123) == "123.0 B"
    assert format_size(1023) == "1023.0 B"

  def test_format_size_kilobytes(self):
    """Test formatting kilobytes"""
    assert format_size(1024) == "1.0 KB"
    assert format_size(1536) == "1.5 KB"  # 1.5 * 1024
    assert format_size(1024 * 1023) == "1023.0 KB"

  def test_format_size_megabytes(self):
    """Test formatting megabytes"""
    assert format_size(1024 * 1024) == "1.0 MB"
    assert format_size(int(2.5 * 1024 * 1024)) == "2.5 MB"

  def test_format_size_gigabytes(self):
    """Test formatting gigabytes"""
    assert format_size(1024 * 1024 * 1024) == "1.0 GB"
    assert format_size(int(1.5 * 1024 * 1024 * 1024)) == "1.5 GB"

  def test_format_size_terabytes(self):
    """Test formatting terabytes"""
    assert format_size(1024**4) == "1.0 TB"

  def test_format_size_petabytes(self):
    """Test formatting petabytes"""
    assert format_size(1024**5) == "1.0 PB"

  def test_format_size_precision(self):
    """Test that formatting uses one decimal place"""
    # Test that we get one decimal place
    result = format_size(1234)
    assert "." in result
    decimal_part = result.split(".")[1].split(" ")[0]
    assert len(decimal_part) == 1


class TestParsePortMapping:
  """Test parse_port_mapping function"""

  def test_parse_port_mapping_single_port(self):
    """Test parsing single port (maps to same port)"""
    host_port, container_port = parse_port_mapping("80")

    assert host_port == 80
    assert container_port == 80

  def test_parse_port_mapping_different_ports(self):
    """Test parsing host:container port mapping"""
    host_port, container_port = parse_port_mapping("8080:80")

    assert host_port == 8080
    assert container_port == 80

  def test_parse_port_mapping_same_ports_explicit(self):
    """Test parsing explicit same ports"""
    host_port, container_port = parse_port_mapping("3000:3000")

    assert host_port == 3000
    assert container_port == 3000

  def test_parse_port_mapping_high_ports(self):
    """Test parsing high port numbers"""
    host_port, container_port = parse_port_mapping("65535:32768")

    assert host_port == 65535
    assert container_port == 32768

  def test_parse_port_mapping_invalid_format(self):
    """Test parsing invalid port format raises ValueError"""
    with pytest.raises(ValueError, match="Invalid port mapping"):
      parse_port_mapping("8080:80:443")

    with pytest.raises(ValueError, match="Invalid port mapping"):
      parse_port_mapping("8080:80:443:22")

  def test_parse_port_mapping_invalid_numbers(self):
    """Test parsing non-numeric ports raises ValueError"""
    with pytest.raises(ValueError):
      parse_port_mapping("abc")

    with pytest.raises(ValueError):
      parse_port_mapping("8080:abc")

    with pytest.raises(ValueError):
      parse_port_mapping("abc:80")

  def test_parse_port_mapping_empty_string(self):
    """Test parsing empty string raises ValueError"""
    with pytest.raises(ValueError):
      parse_port_mapping("")

  def test_parse_port_mapping_edge_cases(self):
    """Test parsing edge case port numbers"""
    # Test port 1 (minimum valid port)
    host_port, container_port = parse_port_mapping("1")
    assert host_port == 1
    assert container_port == 1

    # Test mapping to port 1
    host_port, container_port = parse_port_mapping("8080:1")
    assert host_port == 8080
    assert container_port == 1
