"""
数据库操作层
提供异步数据库访问接口（支持 MySQL 和 SQLite）

依赖：
    SQLite: aiosqlite
    MySQL: aiomysql
安装：pip install aiosqlite aiomysql
"""
import os
import json
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

# 导入配置
import sys
sys.path.insert(0, str(Path(__file__)))
from db_config import DBConfig


class Database:
    """数据库操作类"""

    def __init__(self):
        self.db_type = DBConfig.DB_TYPE
        self._pool = None
        self._conn = None

    async def connect(self):
        """连接数据库"""
        if self.db_type == "mysql":
            import aiomysql
            self._pool = await aiomysql.create_pool(
                host=DBConfig.MYSQL_HOST,
                port=DBConfig.MYSQL_PORT,
                user=DBConfig.MYSQL_USER,
                password=DBConfig.MYSQL_PASSWORD,
                db=DBConfig.MYSQL_DATABASE,
                autocommit=True,
                minsize=1,
                maxsize=5
            )
        else:
            import aiosqlite
            self._conn = await aiosqlite.connect(DBConfig.SQLITE_DB_PATH)
            self._conn.row_factory = aiosqlite.Row

            # 启用外键
            await self._conn.execute("PRAGMA foreign_keys = ON")
            await self._conn.commit()

    async def close(self):
        """关闭数据库连接"""
        if self.db_type == "mysql":
            if self._pool:
                self._pool.close()
                await self._pool.wait_closed()
        else:
            if self._conn:
                await self._conn.close()

    async def _execute(self, query: str, params: tuple = None):
        """执行 SQL 查询"""
        if self.db_type == "mysql":
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params or ())
                    return cursor
        else:
            cursor = await self._conn.execute(query, params or ())
            return cursor

    async def _commit(self):
        """提交事务"""
        if self.db_type == "mysql":
            pass  # MySQL 使用 autocommit
        else:
            await self._conn.commit()

    async def _fetchone(self, cursor):
        """获取一行数据"""
        if self.db_type == "mysql":
            row = await cursor.fetchone()
            return dict(zip([d[0] for d in cursor.description], row)) if row else None
        else:
            return await cursor.fetchone()

    async def _fetchall(self, cursor):
        """获取所有数据"""
        if self.db_type == "mysql":
            rows = await cursor.fetchall()
            return [dict(zip([d[0] for d in cursor.description], row)) for row in rows]
        else:
            return await cursor.fetchall()

    # ==================== 对话记录管理 ====================

    async def save_conversation(
        self,
        device_id: str,
        user_message: str,
        ai_message: str,
        session_id: str = None,
        duration_ms: int = None,
        tokens_used: int = None,
        context_messages: List[Dict] = None,
        request_data: Dict = None,
        response_data: Dict = None,
        model_name: str = None,
        temperature: float = None,
        max_tokens: int = None,
        finish_reason: str = None,
        total_tokens: int = None,
        prompt_tokens: int = None,
        completion_tokens: int = None,
        is_stream: bool = False,
        error_message: str = None,
        metadata: Dict = None
    ) -> int:
        """保存对话记录（完整记录）"""
        if self.db_type == "mysql":
            sql = """
            INSERT INTO conversation_records
            (device_id, session_id, user_message, ai_message, duration_ms, tokens_used,
             context_messages, request_data, response_data, model_name, temperature,
             max_tokens, finish_reason, total_tokens, prompt_tokens, completion_tokens,
             is_stream, error_message, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                device_id, session_id, user_message, ai_message, duration_ms, tokens_used,
                json.dumps(context_messages) if context_messages else None,
                json.dumps(request_data) if request_data else None,
                json.dumps(response_data) if response_data else None,
                model_name, temperature, max_tokens, finish_reason,
                total_tokens, prompt_tokens, completion_tokens,
                1 if is_stream else 0, error_message,
                json.dumps(metadata) if metadata else None
            )
        else:
            sql = """
            INSERT INTO conversation_records
            (device_id, session_id, user_message, ai_message, duration_ms, tokens_used,
             context_messages, request_data, response_data, model_name, temperature,
             max_tokens, finish_reason, total_tokens, prompt_tokens, completion_tokens,
             is_stream, error_message, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                device_id, session_id, user_message, ai_message, duration_ms, tokens_used,
                json.dumps(context_messages) if context_messages else None,
                json.dumps(request_data) if request_data else None,
                json.dumps(response_data) if response_data else None,
                model_name, temperature, max_tokens, finish_reason,
                total_tokens, prompt_tokens, completion_tokens,
                1 if is_stream else 0, error_message,
                json.dumps(metadata) if metadata else None
            )

        cursor = await self._execute(sql, params)
        await self._commit()
        return cursor.lastrowid

    async def get_recent_conversations(self, device_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近 N 条对话记录"""
        if self.db_type == "mysql":
            sql = """
            SELECT id, device_id, session_id, user_message, ai_message,
                   duration_ms, tokens_used, created_at
            FROM conversation_records
            WHERE device_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """
            params = (device_id, limit)
        else:
            sql = """
            SELECT id, device_id, session_id, user_message, ai_message,
                   duration_ms, tokens_used, created_at
            FROM conversation_records
            WHERE device_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """
            params = (device_id, limit)
        
        cursor = await self._execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_conversation_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """获取指定会话的所有对话"""
        if self.db_type == "mysql":
            sql = """
            SELECT id, device_id, user_message, ai_message, created_at
            FROM conversation_records
            WHERE session_id = %s
            ORDER BY created_at ASC
            """
            params = (session_id,)
        else:
            sql = """
            SELECT id, device_id, user_message, ai_message, created_at
            FROM conversation_records
            WHERE session_id = ?
            ORDER BY created_at ASC
            """
            params = (session_id,)
        
        cursor = await self._execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def delete_old_conversations(self, device_id: str, days: int = 30) -> int:
        """删除指定天数之前的对话记录"""
        cutoff_date = datetime.now() - timedelta(days=days)
        if self.db_type == "mysql":
            sql = "DELETE FROM conversation_records WHERE device_id = %s AND created_at < %s"
            params = (device_id, cutoff_date.isoformat())
        else:
            sql = "DELETE FROM conversation_records WHERE device_id = ? AND created_at < ?"
            params = (device_id, cutoff_date.isoformat())
        
        cursor = await self._execute(sql, params)
        await self._commit()
        return cursor.rowcount

    # ==================== 对话摘要管理 ====================

    async def save_summary(
        self, device_id: str, summary_type: str, summary_text: str,
        start_date: date, end_date: date, key_points: Dict = None,
        conversation_count: int = 0
    ) -> int:
        """保存对话摘要"""
        if self.db_type == "mysql":
            sql = """
            INSERT INTO conversation_summaries
            (device_id, summary_type, summary_text, key_points,
             start_date, end_date, conversation_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                device_id, summary_type, summary_text,
                json.dumps(key_points) if key_points else None,
                start_date.isoformat(), end_date.isoformat(), conversation_count
            )
        else:
            sql = """
            INSERT INTO conversation_summaries
            (device_id, summary_type, summary_text, key_points,
             start_date, end_date, conversation_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                device_id, summary_type, summary_text,
                json.dumps(key_points) if key_points else None,
                start_date.isoformat(), end_date.isoformat(), conversation_count
            )
        
        cursor = await self._execute(sql, params)
        await self._commit()
        return cursor.lastrowid

    async def get_latest_summary(self, device_id: str, summary_type: str = "daily") -> Optional[Dict[str, Any]]:
        """获取最新摘要"""
        if self.db_type == "mysql":
            sql = """
            SELECT * FROM conversation_summaries
            WHERE device_id = %s AND summary_type = %s
            ORDER BY end_date DESC
            LIMIT 1
            """
            params = (device_id, summary_type)
        else:
            sql = """
            SELECT * FROM conversation_summaries
            WHERE device_id = ? AND summary_type = ?
            ORDER BY end_date DESC
            LIMIT 1
            """
            params = (device_id, summary_type)
        
        cursor = await self._execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_summaries_in_range(self, device_id: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """获取指定日期范围内的摘要"""
        if self.db_type == "mysql":
            sql = """
            SELECT * FROM conversation_summaries
            WHERE device_id = %s AND start_date >= %s AND end_date <= %s
            ORDER BY start_date DESC
            """
            params = (device_id, start_date.isoformat(), end_date.isoformat())
        else:
            sql = """
            SELECT * FROM conversation_summaries
            WHERE device_id = ? AND start_date >= ? AND end_date <= ?
            ORDER BY start_date DESC
            """
            params = (device_id, start_date.isoformat(), end_date.isoformat())
        
        cursor = await self._execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # ==================== 设备管理 ====================

    async def register_device(self, device_id: str, device_name: str = "智能玩具", device_type: str = "unknown") -> int:
        """注册新设备"""
        if self.db_type == "mysql":
            sql = "INSERT IGNORE INTO devices (device_id, device_name, device_type) VALUES (%s, %s, %s)"
            params = (device_id, device_name, device_type)
        else:
            sql = "INSERT OR IGNORE INTO devices (device_id, device_name, device_type) VALUES (?, ?, ?)"
            params = (device_id, device_name, device_type)
        
        cursor = await self._execute(sql, params)
        await self._commit()
        return cursor.lastrowid

    async def update_device_status(self, device_id: str, last_seen: datetime = None,
                                   battery_level: int = None, wifi_signal: int = None):
        """更新设备状态"""
        if self.db_type == "mysql":
            sql = """
            UPDATE devices
            SET last_seen = %s, battery_level = %s, wifi_signal = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE device_id = %s
            """
            params = (
                last_seen.isoformat() if last_seen else None,
                battery_level, wifi_signal, device_id
            )
        else:
            sql = """
            UPDATE devices
            SET last_seen = ?, battery_level = ?, wifi_signal = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE device_id = ?
            """
            params = (
                last_seen.isoformat() if last_seen else None,
                battery_level, wifi_signal, device_id
            )
        
        await self._execute(sql, params)
        await self._commit()

    async def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """获取设备信息"""
        if self.db_type == "mysql":
            sql = "SELECT * FROM devices WHERE device_id = %s"
            params = (device_id,)
        else:
            sql = "SELECT * FROM devices WHERE device_id = ?"
            params = (device_id,)
        
        cursor = await self._execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_all_devices(self) -> List[Dict[str, Any]]:
        """获取所有设备"""
        if self.db_type == "mysql":
            sql = "SELECT * FROM devices ORDER BY created_at DESC"
            params = ()
        else:
            sql = "SELECT * FROM devices ORDER BY created_at DESC"
            params = ()
        
        cursor = await self._execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # ==================== 用户偏好管理 ====================

    async def save_preferences(self, device_id: str, preferences: Dict[str, Any]):
        """保存用户偏好"""
        if self.db_type == "mysql":
            sql = """
            INSERT INTO user_preferences
            (device_id, child_name, child_age, favorite_topics,
             voice_speed, voice_pitch, preferred_tts_voice, bedtime_mode,
             learning_mode, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
            child_name = VALUES(child_name), child_age = VALUES(child_age),
            favorite_topics = VALUES(favorite_topics), voice_speed = VALUES(voice_speed),
            voice_pitch = VALUES(voice_pitch), preferred_tts_voice = VALUES(preferred_tts_voice),
            bedtime_mode = VALUES(bedtime_mode), learning_mode = VALUES(learning_mode),
            updated_at = CURRENT_TIMESTAMP
            """
            params = (
                device_id, preferences.get('child_name'), preferences.get('child_age'),
                json.dumps(preferences.get('favorite_topics', [])),
                preferences.get('voice_speed', '+0%'), preferences.get('voice_pitch', '+0%'),
                preferences.get('preferred_tts_voice'), preferences.get('bedtime_mode', False),
                preferences.get('learning_mode', False)
            )
        else:
            sql = """
            INSERT OR REPLACE INTO user_preferences
            (device_id, child_name, child_age, favorite_topics,
             voice_speed, voice_pitch, preferred_tts_voice, bedtime_mode,
             learning_mode, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """
            params = (
                device_id, preferences.get('child_name'), preferences.get('child_age'),
                json.dumps(preferences.get('favorite_topics', [])),
                preferences.get('voice_speed', '+0%'), preferences.get('voice_pitch', '+0%'),
                preferences.get('preferred_tts_voice'), preferences.get('bedtime_mode', False),
                preferences.get('learning_mode', False)
            )
        
        await self._execute(sql, params)
        await self._commit()

    async def get_preferences(self, device_id: str) -> Optional[Dict[str, Any]]:
        """获取用户偏好"""
        if self.db_type == "mysql":
            sql = "SELECT * FROM user_preferences WHERE device_id = %s"
            params = (device_id,)
        else:
            sql = "SELECT * FROM user_preferences WHERE device_id = ?"
            params = (device_id,)
        
        cursor = await self._execute(sql, params)
        row = await cursor.fetchone()

        if row:
            data = dict(row)
            if data.get('favorite_topics'):
                data['favorite_topics'] = json.loads(data['favorite_topics'])
            return data
        return None

    # ==================== TTS/ASR 日志管理 ====================

    async def log_tts(self, device_id: str, text_content: str,
                      audio_duration_ms: int = None, file_size: int = None,
                      provider: str = "edge-tts", voice_name: str = None,
                      success: bool = True, error_message: str = None):
        """记录 TTS 合成日志"""
        if self.db_type == "mysql":
            sql = """
            INSERT INTO tts_logs
            (device_id, text_content, audio_duration_ms, file_size,
             provider, voice_name, success, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (device_id, text_content, audio_duration_ms, file_size,
                      provider, voice_name, 1 if success else 0, error_message)
        else:
            sql = """
            INSERT INTO tts_logs
            (device_id, text_content, audio_duration_ms, file_size,
             provider, voice_name, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (device_id, text_content, audio_duration_ms, file_size,
                      provider, voice_name, 1 if success else 0, error_message)
        
        await self._execute(sql, params)
        await self._commit()

    async def log_asr(self, device_id: str, audio_duration_ms: int,
                      recognized_text: str, confidence: float = None,
                      provider: str = "whisper", success: bool = True,
                      error_message: str = None):
        """记录 ASR 识别日志"""
        if self.db_type == "mysql":
            sql = """
            INSERT INTO asr_logs
            (device_id, audio_duration_ms, recognized_text, confidence,
             provider, success, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            params = (device_id, audio_duration_ms, recognized_text,
                      confidence, provider, 1 if success else 0, error_message)
        else:
            sql = """
            INSERT INTO asr_logs
            (device_id, audio_duration_ms, recognized_text, confidence,
             provider, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            params = (device_id, audio_duration_ms, recognized_text,
                      confidence, provider, 1 if success else 0, error_message)
        
        await self._execute(sql, params)
        await self._commit()

    # ==================== 系统配置管理 ====================

    async def get_config(self, key: str, default: str = None) -> Optional[str]:
        """获取系统配置"""
        if self.db_type == "mysql":
            sql = "SELECT config_value FROM system_config WHERE config_key = %s"
            params = (key,)
        else:
            sql = "SELECT config_value FROM system_config WHERE config_key = ?"
            params = (key,)
        
        cursor = await self._execute(sql, params)
        row = await cursor.fetchone()
        return row['config_value'] if row else default

    async def set_config(self, key: str, value: str, description: str = None):
        """设置系统配置"""
        if self.db_type == "mysql":
            if description:
                sql = """
                INSERT INTO system_config
                (config_key, config_value, description, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                config_value = VALUES(config_value),
                description = VALUES(description),
                updated_at = CURRENT_TIMESTAMP
                """
                params = (key, value, description)
            else:
                sql = """
                INSERT INTO system_config
                (config_key, config_value, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                config_value = VALUES(config_value),
                updated_at = CURRENT_TIMESTAMP
                """
                params = (key, value)
        else:
            if description:
                sql = """
                INSERT OR REPLACE INTO system_config
                (config_key, config_value, description, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """
                params = (key, value, description)
            else:
                sql = """
                INSERT OR REPLACE INTO system_config
                (config_key, config_value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """
                params = (key, value)
        
        await self._execute(sql, params)
        await self._commit()

    # ==================== 统计查询 ====================

    async def get_device_stats(self, device_id: str) -> Dict[str, Any]:
        """获取设备统计数据"""
        if self.db_type == "mysql":
            sql = "SELECT * FROM v_device_stats WHERE device_id = %s"
            params = (device_id,)
        else:
            sql = "SELECT * FROM v_device_stats WHERE device_id = ?"
            params = (device_id,)
        
        cursor = await self._execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else {}

    async def get_total_conversations(self, device_id: str = None) -> int:
        """获取对话总数"""
        if self.db_type == "mysql":
            if device_id:
                sql = "SELECT COUNT(*) FROM conversation_records WHERE device_id = %s"
                params = (device_id,)
            else:
                sql = "SELECT COUNT(*) FROM conversation_records"
                params = ()
        else:
            if device_id:
                sql = "SELECT COUNT(*) FROM conversation_records WHERE device_id = ?"
                params = (device_id,)
            else:
                sql = "SELECT COUNT(*) FROM conversation_records"
                params = ()
        
        cursor = await self._execute(sql, params)
        row = await cursor.fetchone()
        return row[0] if row else 0

    # ==================== AI API 日志管理 ====================

    async def log_ai_request(
        self, device_id: str, request_id: str, request_body: Dict,
        response_body: Dict = None, response_status: int = None,
        duration_ms: int = None, is_success: bool = True,
        error_message: str = None, error_type: str = None,
        session_id: str = None, conversation_id: int = None,
        provider: str = 'zhipu', endpoint: str = None, model: str = None,
        api_key_prefix: str = None, request_messages_count: int = None,
        request_system_prompt: str = None, request_user_message: str = None,
        request_context: str = None, response_content: str = None,
        response_finish_reason: str = None, usage_total_tokens: int = None,
        usage_prompt_tokens: int = None, usage_completion_tokens: int = None,
        is_stream: bool = False, stream_chunks_count: int = None,
        request_start_time: datetime = None, request_end_time: datetime = None
    ) -> int:
        """记录 AI API 请求和响应"""
        request_headers = {"Content-Type": "application/json"}
        
        if self.db_type == "mysql":
            sql = """
            INSERT INTO ai_api_logs
            (request_id, device_id, session_id, conversation_id,
             provider, endpoint, model, api_key_prefix,
             request_method, request_headers, request_body,
             request_messages_count, request_system_prompt, request_user_message, request_context,
             response_status, response_headers, response_body,
             response_content, response_finish_reason,
             usage_total_tokens, usage_prompt_tokens, usage_completion_tokens,
             request_start_time, request_end_time, duration_ms,
             is_success, error_type, error_message,
             is_stream, stream_chunks_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                request_id, device_id, session_id, conversation_id,
                provider, endpoint, model, api_key_prefix,
                'POST', json.dumps(request_headers), json.dumps(request_body),
                request_messages_count, request_system_prompt, request_user_message,
                json.dumps(request_context) if request_context else None,
                response_status, None, json.dumps(response_body) if response_body else None,
                response_content, response_finish_reason,
                usage_total_tokens, usage_prompt_tokens, usage_completion_tokens,
                request_start_time.isoformat() if request_start_time else None,
                request_end_time.isoformat() if request_end_time else None,
                duration_ms,
                1 if is_success else 0, error_type, error_message,
                1 if is_stream else 0, stream_chunks_count
            )
        else:
            sql = """
            INSERT INTO ai_api_logs
            (request_id, device_id, session_id, conversation_id,
             provider, endpoint, model, api_key_prefix,
             request_method, request_headers, request_body,
             request_messages_count, request_system_prompt, request_user_message, request_context,
             response_status, response_headers, response_body,
             response_content, response_finish_reason,
             usage_total_tokens, usage_prompt_tokens, usage_completion_tokens,
             request_start_time, request_end_time, duration_ms,
             is_success, error_type, error_message,
             is_stream, stream_chunks_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                request_id, device_id, session_id, conversation_id,
                provider, endpoint, model, api_key_prefix,
                'POST', json.dumps(request_headers), json.dumps(request_body),
                request_messages_count, request_system_prompt, request_user_message,
                json.dumps(request_context) if request_context else None,
                response_status, None, json.dumps(response_body) if response_body else None,
                response_content, response_finish_reason,
                usage_total_tokens, usage_prompt_tokens, usage_completion_tokens,
                request_start_time.isoformat() if request_start_time else None,
                request_end_time.isoformat() if request_end_time else None,
                duration_ms,
                1 if is_success else 0, error_type, error_message,
                1 if is_stream else 0, stream_chunks_count
            )
        
        cursor = await self._execute(sql, params)
        await self._commit()
        return cursor.lastrowid

    async def get_ai_logs(
        self, device_id: str = None, session_id: str = None,
        is_success: bool = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """获取 AI API 日志"""
        conditions = []
        params = []

        if device_id:
            conditions.append("device_id = " + ("%s" if self.db_type == "mysql" else "?"))
            params.append(device_id)
        if session_id:
            conditions.append("session_id = " + ("%s" if self.db_type == "mysql" else "?"))
            params.append(session_id)
        if is_success is not None:
            conditions.append("is_success = " + ("%s" if self.db_type == "mysql" else "?"))
            params.append(1 if is_success else 0)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        if self.db_type == "mysql":
            sql = f"SELECT * FROM ai_api_logs {where_clause} ORDER BY created_at DESC LIMIT %s"
        else:
            sql = f"SELECT * FROM ai_api_logs {where_clause} ORDER BY created_at DESC LIMIT ?"
        
        params.append(limit)
        cursor = await self._execute(sql, tuple(params))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_api_usage_stats(
        self, device_id: str = None, start_date: date = None, end_date: date = None
    ) -> Dict[str, Any]:
        """获取 API 使用统计"""
        conditions = []
        params = []

        if device_id:
            conditions.append("device_id = " + ("%s" if self.db_type == "mysql" else "?"))
            params.append(device_id)
        if start_date:
            conditions.append("DATE(created_at) >= " + ("%s" if self.db_type == "mysql" else "?"))
            params.append(start_date.isoformat())
        if end_date:
            conditions.append("DATE(created_at) <= " + ("%s" if self.db_type == "mysql" else "?"))
            params.append(end_date.isoformat())

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        if self.db_type == "mysql":
            sql = f"""
            SELECT
                COUNT(*) as total_requests,
                SUM(CASE WHEN is_success = 1 THEN 1 ELSE 0 END) as successful_requests,
                SUM(CASE WHEN is_success = 0 THEN 1 ELSE 0 END) as failed_requests,
                SUM(usage_total_tokens) as total_tokens,
                AVG(duration_ms) as avg_duration_ms,
                AVG(CASE WHEN is_success = 1 THEN duration_ms END) as avg_success_duration_ms
            FROM ai_api_logs
            {where_clause}
            """
        else:
            sql = f"""
            SELECT
                COUNT(*) as total_requests,
                SUM(CASE WHEN is_success = 1 THEN 1 ELSE 0 END) as successful_requests,
                SUM(CASE WHEN is_success = 0 THEN 1 ELSE 0 END) as failed_requests,
                SUM(usage_total_tokens) as total_tokens,
                AVG(duration_ms) as avg_duration_ms,
                AVG(CASE WHEN is_success = 1 THEN duration_ms END) as avg_success_duration_ms
            FROM ai_api_logs
            {where_clause}
            """
        
        cursor = await self._execute(sql, tuple(params))
        row = await cursor.fetchone()
        return dict(row) if row else {}

    async def cleanup_old_logs(self, days: int = 30) -> int:
        """清理旧的日志记录"""
        cutoff_date = datetime.now() - timedelta(days=days)
        if self.db_type == "mysql":
            sql = "DELETE FROM ai_api_logs WHERE created_at < %s"
            params = (cutoff_date.isoformat(),)
        else:
            sql = "DELETE FROM ai_api_logs WHERE created_at < ?"
            params = (cutoff_date.isoformat(),)
        
        cursor = await self._execute(sql, params)
        await self._commit()
        return cursor.rowcount


# 全局数据库实例
_db_instance: Optional[Database] = None


def get_database() -> Database:
    """获取数据库实例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
