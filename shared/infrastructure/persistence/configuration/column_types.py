from sqlalchemy import Integer, SmallInteger
from sqlalchemy.dialects.mysql import TINYINT

# TINYINT on MySQL (as defined in the database DDL); plain INTEGER on any other dialect.
TinyInt = Integer().with_variant(TINYINT(), "mysql")

# SMALLINT on MySQL (cell and component ids); plain INTEGER on any other dialect, where only INTEGER keys auto-increment
SmallInt = Integer().with_variant(SmallInteger(), "mysql")

# TINYINT(1) on MySQL (small flag or code column such as component.type)
TinyInt1 = Integer().with_variant(TINYINT(1), "mysql")
