from passlib.context import CryptContext
import getpass

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

password = getpass.getpass("Password to hash: ")
print(pwd_context.hash(password))
