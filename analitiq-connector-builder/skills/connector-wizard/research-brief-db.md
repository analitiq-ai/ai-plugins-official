# Database Connector Research Brief

Research the following database system and answer every question below. Use official documentation as the primary source.

## System
- **Name:** {system_name}
- **Documentation URL:** {url, if provided}

## Questions

1. What is the official driver name? (e.g., `postgresql`, `mysql`, `mssql`, `mongodb`, `bigquery`, `snowflake`)
2. What is the default port?
3. Is SSH tunneling commonly supported/needed for this database?
4. What are the standard connection parameters? (host, port, database/schema, username, password)
5. Are there additional required parameters beyond the standard set? (e.g., warehouse for Snowflake, project for BigQuery, schema for Redshift)
6. What SSL/TLS requirements exist? (required by default, optional, certificate-based)
7. Are there any special authentication methods? (IAM auth, Kerberos, certificate-based, token-based)
8. Any special connection string format requirements or caveats?
9. Is this database system (or the specific version/driver) deprecated or end-of-life?

## Expected Output Format

```json
{
  "source_url": "https://docs.example.com/connection",
  "deprecated": false,
  "driver": "postgresql",
  "default_port": "5432",
  "enable_ssh": true,
  "form_fields": [
    { "name": "host", "label": "Host", "type": "text", "required": true },
    { "name": "port", "label": "Port", "type": "text", "required": true, "default": "5432" },
    { "name": "database", "label": "Database", "type": "text", "required": true },
    { "name": "username", "label": "Username", "type": "text", "required": true },
    { "name": "password", "label": "Password", "type": "password", "required": true, "secret": true }
  ],
  "notes": "Any special caveats or additional context"
}
```
