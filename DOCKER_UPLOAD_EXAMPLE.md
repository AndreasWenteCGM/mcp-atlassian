# Uploading Attachments in Docker Environment

When the MCP server runs in a Docker container, it cannot access files on the host filesystem. The Confluence attachment tools now support base64-encoded content to solve this issue.

## Single File Upload

### Using file_path (local filesystem only)
```json
{
  "page_id": "123456",
  "file_path": "/path/to/document.pdf",
  "comment": "Updated documentation"
}
```

### Using base64 content (Docker-compatible)
```json
{
  "page_id": "123456",
  "filename": "document.pdf",
  "content": "JVBERi0xLjQKJeLjz9MKMSAwIG9iag...",
  "comment": "Updated documentation"
}
```

## Multiple Files Upload

### Using file_paths (local filesystem only)
```json
{
  "page_id": "123456",
  "file_paths": [
    "/path/to/document1.pdf",
    "/path/to/document2.pdf"
  ],
  "comment": "Batch upload"
}
```

### Using attachments with base64 content (Docker-compatible)
```json
{
  "page_id": "123456",
  "attachments": [
    {
      "filename": "document1.pdf",
      "content": "JVBERi0xLjQKJeLjz9MK..."
    },
    {
      "filename": "document2.pdf",
      "content": "JVBERi0xLjQKJeabc123..."
    }
  ],
  "comment": "Batch upload"
}
```

## Converting Files to Base64

### Python Example
```python
import base64

# Read file and encode to base64
with open("document.pdf", "rb") as f:
    content = base64.b64encode(f.read()).decode("utf-8")

# Use in MCP tool call
params = {
    "page_id": "123456",
    "filename": "document.pdf",
    "content": content,
}
```

### JavaScript/Node.js Example
```javascript
const fs = require('fs');

// Read file and encode to base64
const fileBuffer = fs.readFileSync('document.pdf');
const content = fileBuffer.toString('base64');

// Use in MCP tool call
const params = {
  page_id: "123456",
  filename: "document.pdf",
  content: content,
};
```

### Bash Example
```bash
# Encode file to base64
content=$(base64 -w 0 document.pdf)

# Use in MCP tool call (JSON)
cat <<EOF
{
  "page_id": "123456",
  "filename": "document.pdf",
  "content": "$content"
}
EOF
```

## Important Notes

1. **Choose one mode**: You cannot use both `file_path` and `content` in the same call
2. **Filename required**: When using `content`, you must provide the `filename` parameter
3. **Base64 encoding**: Content must be base64-encoded binary data
4. **Size limits**: Be aware of Confluence attachment size limits (typically 10-100 MB)
5. **Memory usage**: Base64-encoded content is ~33% larger than the original file

## Error Handling

The tools validate parameters and return clear error messages:

- `"Either file_path or (filename + content) must be provided"` - Missing required parameters
- `"Cannot specify both file_path and content"` - Conflicting parameters provided
- `"File not found: /path/to/file"` - File doesn't exist (file_path mode)
- Base64 decode errors - Invalid base64 encoding in content parameter
