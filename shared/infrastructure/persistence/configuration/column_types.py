from sqlalchemy import Integer
from sqlalchemy.dialects.mysql import TINYINT

# TINYINT on MySQL (as defined in the database DDL); plain INTEGER on any other dialect.
TinyInt = Integer().with_variant(TINYINT(), "mysql")
