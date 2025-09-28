"""
Advanced Caching Module for Archon
Provides Redis/ElastiCache integration with fallback to DynamoDB and in-memory caching
"""

import json
import time
import hashlib
import logging
from typing import Any, Optional, Dict, Union
from dataclasses import dataclass, asdict
from enum import Enum

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class CacheBackend(Enum):
    """Cache backend types"""
    REDIS = "redis"
    DYNAMODB = "dynamodb"
    MEMORY = "memory"

@dataclass
class CacheConfig:
    """Cache configuration"""
    backend: CacheBackend = CacheBackend.DYNAMODB
    ttl_seconds: int = 3600
    max_memory_items: int = 1000
    redis_endpoint: Optional[str] = None
    dynamodb_table: str = "archon-cache"
    key_prefix: str = "archon"

@dataclass
class CacheItem:
    """Cache item structure"""
    key: str
    value: Any
    created_at: float
    expires_at: float
    hits: int = 0
    
    def is_expired(self) -> bool:
        """Check if item is expired"""
        return time.time() > self.expires_at
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage"""
        return {
            "key": self.key,
            "value": json.dumps(self.value) if not isinstance(self.value, str) else self.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "hits": self.hits
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CacheItem':
        """Create from dictionary"""
        try:
            value = json.loads(data["value"])
        except (json.JSONDecodeError, TypeError):
            value = data["value"]
        
        return cls(
            key=data["key"],
            value=value,
            created_at=data["created_at"],
            expires_at=data["expires_at"],
            hits=data.get("hits", 0)
        )

class RedisCache:
    """Redis cache implementation"""
    
    def __init__(self, endpoint: str, port: int = 6379):
        self.endpoint = endpoint
        self.port = port
        self._client = None
        self._connect()
    
    def _connect(self):
        """Connect to Redis"""
        try:
            import redis
            self._client = redis.Redis(
                host=self.endpoint,
                port=self.port,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # Test connection
            self._client.ping()
            logger.info(f"Connected to Redis at {self.endpoint}:{self.port}")
        except ImportError:
            logger.error("Redis library not installed. Install with: pip install redis")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def get(self, key: str) -> Optional[CacheItem]:
        """Get item from Redis"""
        try:
            data = self._client.get(key)
            if data:
                item_data = json.loads(data)
                return CacheItem.from_dict(item_data)
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
        return None
    
    def set(self, key: str, item: CacheItem) -> bool:
        """Set item in Redis"""
        try:
            data = json.dumps(item.to_dict())
            ttl = int(item.expires_at - time.time())
            if ttl > 0:
                self._client.setex(key, ttl, data)
            else:
                self._client.set(key, data)
            return True
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete item from Redis"""
        try:
            self._client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            return False

class DynamoDBCache:
    """DynamoDB cache implementation"""
    
    def __init__(self, table_name: str):
        self.table_name = table_name
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
    
    def get(self, key: str) -> Optional[CacheItem]:
        """Get item from DynamoDB"""
        try:
            response = self.table.get_item(Key={'cache_key': key})
            if 'Item' in response:
                return CacheItem.from_dict(response['Item'])
        except ClientError as e:
            logger.error(f"DynamoDB get error for key {key}: {e}")
        return None
    
    def set(self, key: str, item: CacheItem) -> bool:
        """Set item in DynamoDB"""
        try:
            item_data = item.to_dict()
            item_data['cache_key'] = key
            item_data['ttl'] = int(item.expires_at)
            
            self.table.put_item(Item=item_data)
            return True
        except ClientError as e:
            logger.error(f"DynamoDB set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete item from DynamoDB"""
        try:
            self.table.delete_item(Key={'cache_key': key})
            return True
        except ClientError as e:
            logger.error(f"DynamoDB delete error for key {key}: {e}")
            return False

class MemoryCache:
    """In-memory cache implementation"""
    
    def __init__(self, max_items: int = 1000):
        self.max_items = max_items
        self._cache: Dict[str, CacheItem] = {}
        self._access_times: Dict[str, float] = {}
    
    def get(self, key: str) -> Optional[CacheItem]:
        """Get item from memory cache"""
        if key in self._cache:
            item = self._cache[key]
            if not item.is_expired():
                item.hits += 1
                self._access_times[key] = time.time()
                return item
            else:
                # Remove expired item
                del self._cache[key]
                if key in self._access_times:
                    del self._access_times[key]
        return None
    
    def set(self, key: str, item: CacheItem) -> bool:
        """Set item in memory cache"""
        # Evict oldest items if cache is full
        if len(self._cache) >= self.max_items and key not in self._cache:
            self._evict_oldest()
        
        self._cache[key] = item
        self._access_times[key] = time.time()
        return True
    
    def delete(self, key: str) -> bool:
        """Delete item from memory cache"""
        if key in self._cache:
            del self._cache[key]
        if key in self._access_times:
            del self._access_times[key]
        return True
    
    def _evict_oldest(self):
        """Evict oldest accessed item"""
        if not self._access_times:
            return
        
        oldest_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
        del self._cache[oldest_key]
        del self._access_times[oldest_key]

class AdvancedCache:
    """Advanced cache with multiple backends and fallback"""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.backends = []
        self._initialize_backends()
    
    def _initialize_backends(self):
        """Initialize cache backends in priority order"""
        if self.config.backend == CacheBackend.REDIS and self.config.redis_endpoint:
            try:
                redis_cache = RedisCache(self.config.redis_endpoint)
                self.backends.append(redis_cache)
                logger.info("Redis cache backend initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis cache: {e}")
        
        # Always add DynamoDB as fallback
        try:
            dynamodb_cache = DynamoDBCache(self.config.dynamodb_table)
            self.backends.append(dynamodb_cache)
            logger.info("DynamoDB cache backend initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize DynamoDB cache: {e}")
        
        # Add memory cache as last resort
        memory_cache = MemoryCache(self.config.max_memory_items)
        self.backends.append(memory_cache)
        logger.info("Memory cache backend initialized")
    
    def _generate_key(self, namespace: str, *args, **kwargs) -> str:
        """Generate cache key from namespace and arguments"""
        key_data = {
            "namespace": namespace,
            "args": args,
            "kwargs": sorted(kwargs.items())
        }
        key_string = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"{self.config.key_prefix}:{namespace}:{key_hash}"
    
    def get(self, namespace: str, *args, **kwargs) -> Optional[Any]:
        """Get cached value"""
        key = self._generate_key(namespace, *args, **kwargs)
        
        for backend in self.backends:
            try:
                item = backend.get(key)
                if item and not item.is_expired():
                    logger.debug(f"Cache hit for key {key} in {type(backend).__name__}")
                    return item.value
            except Exception as e:
                logger.warning(f"Cache get error in {type(backend).__name__}: {e}")
                continue
        
        logger.debug(f"Cache miss for key {key}")
        return None
    
    def set(self, namespace: str, value: Any, ttl_seconds: Optional[int] = None, *args, **kwargs) -> bool:
        """Set cached value"""
        key = self._generate_key(namespace, *args, **kwargs)
        ttl = ttl_seconds or self.config.ttl_seconds
        
        item = CacheItem(
            key=key,
            value=value,
            created_at=time.time(),
            expires_at=time.time() + ttl
        )
        
        success = False
        for backend in self.backends:
            try:
                if backend.set(key, item):
                    success = True
                    logger.debug(f"Cached value for key {key} in {type(backend).__name__}")
            except Exception as e:
                logger.warning(f"Cache set error in {type(backend).__name__}: {e}")
                continue
        
        return success
    
    def delete(self, namespace: str, *args, **kwargs) -> bool:
        """Delete cached value"""
        key = self._generate_key(namespace, *args, **kwargs)
        
        success = False
        for backend in self.backends:
            try:
                if backend.delete(key):
                    success = True
            except Exception as e:
                logger.warning(f"Cache delete error in {type(backend).__name__}: {e}")
                continue
        
        return success
    
    def clear(self, namespace: Optional[str] = None) -> bool:
        """Clear cache (memory backend only)"""
        if namespace:
            # Clear specific namespace (memory backend only)
            keys_to_remove = [key for key in self.backends[-1]._cache.keys() 
                             if key.startswith(f"{self.config.key_prefix}:{namespace}:")]
            for key in keys_to_remove:
                self.backends[-1].delete(key)
        else:
            # Clear all (memory backend only)
            self.backends[-1]._cache.clear()
            self.backends[-1]._access_times.clear()
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            "backends": len(self.backends),
            "backend_types": [type(backend).__name__ for backend in self.backends]
        }
        
        # Get memory cache stats
        if self.backends and isinstance(self.backends[-1], MemoryCache):
            memory_cache = self.backends[-1]
            stats["memory_cache"] = {
                "items": len(memory_cache._cache),
                "max_items": memory_cache.max_items,
                "hit_rates": {key: item.hits for key, item in memory_cache._cache.items()}
            }
        
        return stats

# Global cache instance
_cache_instance: Optional[AdvancedCache] = None

def get_cache() -> AdvancedCache:
    """Get global cache instance"""
    global _cache_instance
    if _cache_instance is None:
        config = CacheConfig()
        _cache_instance = AdvancedCache(config)
    return _cache_instance

def cache_result(namespace: str, ttl_seconds: Optional[int] = None):
    """Decorator for caching function results"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Try to get from cache
            cached_result = cache.get(namespace, *args, **kwargs)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(namespace, result, ttl_seconds, *args, **kwargs)
            return result
        
        return wrapper
    return decorator
