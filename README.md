# django_mysql_utils

用于django将verbose_name添加到mysql备注以及修改datetime(6)为datetime(0)

# 使用

直接复制到django项目中在INSTALLED_APPS中添加该项目

```python
INSTALLED_APPS = [
    'django_mysql_utils'
]
```

执行完数据库迁移后执行该命令即可

```shell
python .\manage.py django_mysql_utils
```
