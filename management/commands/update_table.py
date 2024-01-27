"""
commands 'python manage.py addcolumncomments'
"""
from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections
from django.apps import apps


class Command(BaseCommand):
    help = '给mysql数据库字段添加备注,以及修改datetime的长度'

    def add_arguments(self, parser):
        # 增加数据库配置
        parser.add_argument(
            '--database',
            default=DEFAULT_DB_ALIAS,
            help='Nominates a database to synchronize. Defaults to the "default" database.',
        )

    def handle(self, *args, **options):
        # 1. 连接数据库
        connection = self.get_db_connection(options)
        cursor = connection.cursor()
        # 2. 获取所有的模型
        models = apps.get_models()
        custom_models = [model for model in models if 'django.contrib' not in str(model)]
        # 3. know the database type
        connection_type_info = str(connection)
        processed = False
        if "mysql" in connection_type_info:
            self.mysql_add_comment(cursor, connection, custom_models)
            processed = True
            self.mysql_update_datetime(cursor, connection, custom_models)
        if not processed:
            self.stdout.write(f"no related type for {connection_type_info}, now only support mysql and postgresql")

        connection.close()

    # 获取数据库连接
    def get_db_connection(self, options):
        database = options['database']
        connection = connections[database]
        connection.prepare_database()
        return connection

    def is_field_type_to_be_processed(self, field):
        """
        the filed_type may be: Char, Integer, AutoField or Foreign,
        and the AutoField, Foreign will not be processed
        """
        field_type = str(type(field))
        if "AutoField" in str(field_type) or "Foreign" in str(field_type):
            return False
        return True

    def get_comment_text(self, field, db_column):
        """
        first verbose_name as comment, then help text
        """
        comment_text = field.verbose_name
        if not comment_text or comment_text == db_column.replace("_", " "):
            comment_text = field.help_text
        return comment_text

    def mysql_add_comment(self, cursor, connection, custom_models):
        for model_obj in custom_models:
            if not model_obj._meta.managed:
                continue
            # 2.1 获取table_name
            table_name = model_obj._meta.db_table
            # 2.2 从数据库中获取 ddl of create table ...
            ddl_sql = "show create table " + table_name
            cursor.execute(ddl_sql)
            ddl_result = cursor.fetchall()
            table_ddl = ddl_result[0][1]
            ddl_texts = table_ddl.split("\n")
            ddl_column_dict = {}
            for ddl_text in ddl_texts:
                ddl_text = ddl_text.strip()

                # 找到属于字段的行
                if ddl_text[0] == '`':
                    next_index = ddl_text.index("`", 1, len(ddl_text))
                    column_key = ddl_text[1: next_index]
                    if column_key == 'id':
                        continue
                    # 移除 comment
                    comment_index = ddl_text.find("COMMENT")
                    ddl_column_dict[column_key] = ddl_text[0:comment_index]

            # 3. 遍历model的字段
            fields = model_obj._meta.fields
            for field in fields:
                db_column = field.db_column
                if not db_column:
                    db_column = field.name

                # 3.1 get verbose_name as comment
                comment_text = self.get_comment_text(field, db_column)
                if not comment_text:
                    continue
                model_comment_sql = "-- FOR " + table_name + "." + db_column + " \n"
                model_comment_sql += "\t" + "ALTER TABLE " + table_name + "\n"
                model_comment_sql += "\t" + "MODIFY COLUMN "
                if not self.is_field_type_to_be_processed(field):
                    continue
                original_ddl = ddl_column_dict.get(db_column)
                model_comment_sql += original_ddl + " COMMENT '" + str(comment_text) + "'"
                self.stdout.write(model_comment_sql)
                cursor.execute(model_comment_sql)
                connection.commit()

    def mysql_update_datetime(self, cursor, connection, custom_models):
        for model_obj in custom_models:
            if not model_obj._meta.managed:
                continue
            # 2.1 获取table_name
            table_name = model_obj._meta.db_table
            # 2.2 从数据库中获取 ddl of create table ...
            ddl_sql = "show create table " + table_name
            cursor.execute(ddl_sql)
            ddl_result = cursor.fetchall()
            table_ddl = ddl_result[0][1]
            ddl_texts = table_ddl.split("\n")
            time_filed = []
            ddl_column_dict = {}
            for ddl_text in ddl_texts:
                ddl_text = ddl_text.strip()

                # 找到属于字段的行
                if ddl_text[0] == '`':
                    next_index = ddl_text.index("`", 1, len(ddl_text))
                    column_key = ddl_text[1: next_index]
                    if column_key == 'id':
                        continue
                    # 移除 comment
                    comment_index = ddl_text.find("COMMENT")
                    ddl_column_dict[column_key] = ddl_text[0:comment_index]

                    if "datetime(6)" in ddl_text:
                        time_filed.append(column_key)

            # 3. 遍历model的字段
            fields = model_obj._meta.fields
            for field in fields:
                db_column = field.db_column
                if not db_column:
                    db_column = field.name

                # 如果存在于datetime(6)的字段
                if db_column not in time_filed:
                    continue
                model_comment_sql = "-- FOR " + table_name + "." + db_column + " \n"
                model_comment_sql += "\t" + "ALTER TABLE " + table_name + "\n"
                model_comment_sql += "\t" + "MODIFY COLUMN "

                if not self.is_field_type_to_be_processed(field):
                    continue

                original_ddl = ddl_column_dict.get(db_column)
                original_ddl = original_ddl.replace("datetime(6)", "datetime(0)")
                model_comment_sql += original_ddl

                self.stdout.write(model_comment_sql)
                cursor.execute(model_comment_sql)
                connection.commit()
