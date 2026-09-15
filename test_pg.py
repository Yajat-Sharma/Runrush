import pg8000.native
import ssl

try:
    print("Attempting to connect with pg8000 (with SSL)...")
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    conn = pg8000.native.Connection(
        user="runrush_db_user",
        password="ovkri3f5LYpC640jzmjjDCYzbDabTeaY",
        host="dpg-d9ush97avr4c73be0rig-a.singapore-postgres.render.com",
        database="runrush_db",
        ssl_context=ssl_context
    )
    print("Successfully connected!")
    
    result = conn.run("SELECT version();")
    print("You are connected to -", result[0][0])
    
    conn.close()
except Exception as error:
    print("Error while connecting to PostgreSQL:", error)
