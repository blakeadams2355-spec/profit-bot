import sqlite3
from datetime import datetime, date, timedelta
from typing import Optional
from config import DATABASE_PATH


def get_connection():
    """Получить соединение с БД"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Инициализация базы данных"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Таблица сделок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'RUB',
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            transaction_date DATE NOT NULL
        )
    ''')
    
    # Таблица настроек
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()


# ==================== ТРАНЗАКЦИИ ====================

def add_transaction(amount: float, currency: str, comment: str = None, 
                    transaction_date: date = None) -> int:
    """Добавить транзакцию"""
    if transaction_date is None:
        transaction_date = date.today()
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO transactions (amount, currency, comment, transaction_date)
        VALUES (?, ?, ?, ?)
    ''', (amount, currency, comment, transaction_date.isoformat()))
    
    transaction_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return transaction_id


def delete_transaction(transaction_id: int) -> bool:
    """Удалить транзакцию"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM transactions WHERE id = ?', (transaction_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_transactions(currency: str = None, start_date: date = None, 
                     end_date: date = None, limit: int = None) -> list:
    """Получить транзакции с фильтрами"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = 'SELECT * FROM transactions WHERE 1=1'
    params = []
    
    if currency:
        query += ' AND currency = ?'
        params.append(currency)
    
    if start_date:
        query += ' AND transaction_date >= ?'
        params.append(start_date.isoformat())
    
    if end_date:
        query += ' AND transaction_date <= ?'
        params.append(end_date.isoformat())
    
    query += ' ORDER BY transaction_date DESC, created_at DESC'
    
    if limit:
        query += f' LIMIT {limit}'
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_last_transaction() -> Optional[dict]:
    """Получить последнюю транзакцию"""
    transactions = get_transactions(limit=1)
    return transactions[0] if transactions else None


# ==================== СТАТИСТИКА ====================

def get_stats(currency: str, start_date: date = None, end_date: date = None) -> dict:
    """Получить статистику за период"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT 
            COUNT(*) as count,
            COALESCE(SUM(amount), 0) as total,
            COALESCE(AVG(amount), 0) as average,
            COALESCE(MIN(amount), 0) as min_amount,
            COALESCE(MAX(amount), 0) as max_amount
        FROM transactions 
        WHERE currency = ?
    '''
    params = [currency]
    
    if start_date:
        query += ' AND transaction_date >= ?'
        params.append(start_date.isoformat())
    
    if end_date:
        query += ' AND transaction_date <= ?'
        params.append(end_date.isoformat())
    
    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()
    
    return {
        'count': row['count'],
        'total': row['total'],
        'average': row['average'],
        'min_amount': row['min_amount'],
        'max_amount': row['max_amount']
    }


def get_best_worst_days(currency: str, start_date: date = None, 
                         end_date: date = None) -> dict:
    """Получить лучший и худший дни"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT 
            transaction_date,
            SUM(amount) as daily_total,
            COUNT(*) as deal_count
        FROM transactions 
        WHERE currency = ?
    '''
    params = [currency]
    
    if start_date:
        query += ' AND transaction_date >= ?'
        params.append(start_date.isoformat())
    
    if end_date:
        query += ' AND transaction_date <= ?'
        params.append(end_date.isoformat())
    
    query += ' GROUP BY transaction_date ORDER BY daily_total DESC'
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return {'best': None, 'worst': None}
    
    return {
        'best': dict(rows[0]),
        'worst': dict(rows[-1])
    }


def get_daily_stats(currency: str, start_date: date = None, 
                    end_date: date = None) -> list:
    """Получить статистику по дням для графиков"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT 
            transaction_date,
            SUM(amount) as daily_total,
            COUNT(*) as deal_count
        FROM transactions 
        WHERE currency = ?
    '''
    params = [currency]
    
    if start_date:
        query += ' AND transaction_date >= ?'
        params.append(start_date.isoformat())
    
    if end_date:
        query += ' AND transaction_date <= ?'
        params.append(end_date.isoformat())
    
    query += ' GROUP BY transaction_date ORDER BY transaction_date ASC'
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_monthly_stats(currency: str, year: int = None) -> list:
    """Получить статистику по месяцам"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT 
            strftime('%Y-%m', transaction_date) as month,
            SUM(amount) as monthly_total,
            COUNT(*) as deal_count,
            AVG(amount) as average
        FROM transactions 
        WHERE currency = ?
    '''
    params = [currency]
    
    if year:
        query += " AND strftime('%Y', transaction_date) = ?"
        params.append(str(year))
    
    query += ' GROUP BY month ORDER BY month ASC'
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def compare_periods(currency: str, period1_start: date, period1_end: date,
                    period2_start: date, period2_end: date) -> dict:
    """Сравнить два периода"""
    stats1 = get_stats(currency, period1_start, period1_end)
    stats2 = get_stats(currency, period2_start, period2_end)
    
    # Расчёт динамики
    if stats2['total'] > 0:
        total_change = ((stats1['total'] - stats2['total']) / stats2['total']) * 100
    else:
        total_change = 100 if stats1['total'] > 0 else 0
    
    if stats2['count'] > 0:
        count_change = ((stats1['count'] - stats2['count']) / stats2['count']) * 100
    else:
        count_change = 100 if stats1['count'] > 0 else 0
    
    if stats2['average'] > 0:
        avg_change = ((stats1['average'] - stats2['average']) / stats2['average']) * 100
    else:
        avg_change = 100 if stats1['average'] > 0 else 0
    
    return {
        'period1': stats1,
        'period2': stats2,
        'total_change_percent': total_change,
        'count_change_percent': count_change,
        'average_change_percent': avg_change
    }


# ==================== НАСТРОЙКИ ====================

def get_setting(key: str, default: str = None) -> Optional[str]:
    """Получить настройку"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else default


def set_setting(key: str, value: str):
    """Установить настройку"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
    ''', (key, value))
    conn.commit()
    conn.close()


def get_all_settings() -> dict:
    """Получить все настройки"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT key, value FROM settings')
    rows = cursor.fetchall()
    conn.close()
    return {row['key']: row['value'] for row in rows}


def get_combined_stats(start_date: date = None, end_date: date = None, 
                       rate: float = 100.0) -> dict:
    """Получить объединённую статистику по всем валютам
    
    Args:
        start_date: Начало периода
        end_date: Конец периода
        rate: Курс USD к RUB
    
    Returns:
        Словарь с статистикой в обеих валютах
    """
    rub_stats = get_stats("RUB", start_date, end_date)
    usd_stats = get_stats("USD", start_date, end_date)
    
    # Конвертируем всё в рубли
    usd_in_rub = usd_stats['total'] * rate
    total_rub = rub_stats['total'] + usd_in_rub
    
    # Конвертируем всё в доллары  
    rub_in_usd = rub_stats['total'] / rate if rate > 0 else 0
    total_usd = usd_stats['total'] + rub_in_usd
    
    total_count = rub_stats['count'] + usd_stats['count']
    
    # Средние значения
    avg_rub = total_rub / total_count if total_count > 0 else 0
    avg_usd = total_usd / total_count if total_count > 0 else 0
    
    return {
        'rub': rub_stats,
        'usd': usd_stats,
        'total_rub': total_rub,
        'total_usd': total_usd,
        'total_count': total_count,
        'avg_rub': avg_rub,
        'avg_usd': avg_usd,
        'usd_in_rub': usd_in_rub,
        'rub_in_usd': rub_in_usd,
        'rate': rate
    }


def get_all_transactions(start_date: date = None, end_date: date = None, 
                         limit: int = None) -> list:
    """Получить все транзакции (обе валюты)"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = 'SELECT * FROM transactions WHERE 1=1'
    params = []
    
    if start_date:
        query += ' AND transaction_date >= ?'
        params.append(start_date.isoformat())
    
    if end_date:
        query += ' AND transaction_date <= ?'
        params.append(end_date.isoformat())
    
    query += ' ORDER BY transaction_date DESC, created_at DESC'
    
    if limit:
        query += f' LIMIT {limit}'
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_combined_daily_stats(start_date: date = None, end_date: date = None,
                             rate: float = 100.0) -> list:
    """Получить статистику по дням с конвертацией"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT 
            transaction_date,
            currency,
            SUM(amount) as daily_total,
            COUNT(*) as deal_count
        FROM transactions 
        WHERE 1=1
    '''
    params = []
    
    if start_date:
        query += ' AND transaction_date >= ?'
        params.append(start_date.isoformat())
    
    if end_date:
        query += ' AND transaction_date <= ?'
        params.append(end_date.isoformat())
    
    query += ' GROUP BY transaction_date, currency ORDER BY transaction_date ASC'
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    # Группируем по дням и конвертируем
    daily_data = {}
    for row in rows:
        d = row['transaction_date']
        if d not in daily_data:
            daily_data[d] = {'date': d, 'rub': 0, 'usd': 0, 'total_rub': 0, 'total_usd': 0, 'count': 0}
        
        if row['currency'] == 'RUB':
            daily_data[d]['rub'] = row['daily_total']
        else:
            daily_data[d]['usd'] = row['daily_total']
        daily_data[d]['count'] += row['deal_count']
    
    # Рассчитываем конвертацию
    for d in daily_data:
        daily_data[d]['total_rub'] = daily_data[d]['rub'] + daily_data[d]['usd'] * rate
        daily_data[d]['total_usd'] = daily_data[d]['usd'] + daily_data[d]['rub'] / rate if rate > 0 else 0
    
    return list(daily_data.values())


def get_combined_monthly_stats(rate: float = 100.0, year: int = None) -> list:
    """Получить статистику по месяцам с конвертацией"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT 
            strftime('%Y-%m', transaction_date) as month,
            currency,
            SUM(amount) as monthly_total,
            COUNT(*) as deal_count
        FROM transactions 
        WHERE 1=1
    '''
    params = []
    
    if year:
        query += " AND strftime('%Y', transaction_date) = ?"
        params.append(str(year))
    
    query += ' GROUP BY month, currency ORDER BY month ASC'
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    # Группируем по месяцам
    monthly_data = {}
    for row in rows:
        m = row['month']
        if m not in monthly_data:
            monthly_data[m] = {'month': m, 'rub': 0, 'usd': 0, 'total_rub': 0, 'total_usd': 0, 'count': 0}
        
        if row['currency'] == 'RUB':
            monthly_data[m]['rub'] = row['monthly_total']
        else:
            monthly_data[m]['usd'] = row['monthly_total']
        monthly_data[m]['count'] += row['deal_count']
    
    # Рассчитываем конвертацию
    for m in monthly_data:
        monthly_data[m]['total_rub'] = monthly_data[m]['rub'] + monthly_data[m]['usd'] * rate
        monthly_data[m]['total_usd'] = monthly_data[m]['usd'] + monthly_data[m]['rub'] / rate if rate > 0 else 0
    
    return list(monthly_data.values())


# Инициализация при импорте
init_db()
