#!/usr/bin/env python3

import pymysql


def init_services_db(host, userame, password, database, port=3306):
    try:
        db_conn = pymysql.connect(host=host, port=port, user=userame,password=password)
        db = db_conn.cursor()
        db.execute(f"SHOW DATABASES LIKE '{database}'")
        row = db.fetchall()
        if len(row) == 0:
            db.execute(f"CREATE DATABASE '{database}'")
            db.select_db(f"{database}")
            db.execute(f"CREATE TABLE 'core_services'core_ (checked_at, id, name, status)")

        db.close()
    except Exception as e:
        log.error(f'init_services_db error: {e}')
