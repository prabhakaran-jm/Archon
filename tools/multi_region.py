"""
Multi-Region Support Module for Archon
Provides cross-region deployment and failover capabilities
"""

import json
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class RegionStatus(Enum):
    """Region status enumeration"""
    ACTIVE = "active"
    STANDBY = "standby"
    FAILED = "failed"
    MAINTENANCE = "maintenance"

@dataclass
class RegionConfig:
    """Configuration for a region"""
    region_name: str
    status: RegionStatus
    priority: int  # Lower number = higher priority
    api_gateway_url: Optional[str] = None
    artifacts_bucket: Optional[str] = None
    runs_table: Optional[str] = None
    ecs_cluster: Optional[str] = None
    last_health_check: Optional[float] = None
    health_status: str = "unknown"

@dataclass
class MultiRegionConfig:
    """Multi-region configuration"""
    primary_region: str
    regions: List[RegionConfig]
    failover_enabled: bool = True
    health_check_interval: int = 300  # 5 minutes
    failover_threshold: int = 3  # Failures before failover

class MultiRegionManager:
    """Manages multi-region deployment and failover"""
    
    def __init__(self, config: MultiRegionConfig):
        self.config = config
        self.current_region = config.primary_region
        self.failure_count = 0
        self.last_failover_time = 0
        self._clients: Dict[str, Any] = {}
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize AWS clients for each region"""
        for region_config in self.config.regions:
            try:
                client = boto3.client('lambda', region_name=region_config.region_name)
                self._clients[region_config.region_name] = client
                logger.info(f"Initialized client for region {region_config.region_name}")
            except Exception as e:
                logger.error(f"Failed to initialize client for region {region_config.region_name}: {e}")
    
    def get_active_region(self) -> str:
        """Get currently active region"""
        return self.current_region
    
    def get_region_config(self, region_name: str) -> Optional[RegionConfig]:
        """Get configuration for specific region"""
        for region_config in self.config.regions:
            if region_config.region_name == region_name:
                return region_config
        return None
    
    def check_region_health(self, region_name: str) -> bool:
        """Check health of a specific region"""
        try:
            region_config = self.get_region_config(region_name)
            if not region_config:
                return False
            
            # Check Lambda function health
            if region_config.api_gateway_url:
                import requests
                health_url = f"{region_config.api_gateway_url}/health"
                response = requests.get(health_url, timeout=10)
                if response.status_code == 200:
                    region_config.health_status = "healthy"
                    region_config.last_health_check = time.time()
                    return True
            
            # Check DynamoDB table
            if region_config.runs_table:
                dynamodb = boto3.resource('dynamodb', region_name=region_name)
                table = dynamodb.Table(region_config.runs_table)
                table.describe_table()
            
            # Check S3 bucket
            if region_config.artifacts_bucket:
                s3 = boto3.client('s3', region_name=region_name)
                s3.head_bucket(Bucket=region_config.artifacts_bucket)
            
            region_config.health_status = "healthy"
            region_config.last_health_check = time.time()
            return True
            
        except Exception as e:
            logger.error(f"Health check failed for region {region_name}: {e}")
            region_config = self.get_region_config(region_name)
            if region_config:
                region_config.health_status = "unhealthy"
                region_config.last_health_check = time.time()
            return False
    
    def check_all_regions_health(self) -> Dict[str, bool]:
        """Check health of all regions"""
        health_status = {}
        for region_config in self.config.regions:
            health_status[region_config.region_name] = self.check_region_health(region_config.region_name)
        return health_status
    
    def should_failover(self) -> bool:
        """Determine if failover should occur"""
        if not self.config.failover_enabled:
            return False
        
        # Check if current region is healthy
        if self.check_region_health(self.current_region):
            self.failure_count = 0
            return False
        
        self.failure_count += 1
        
        # Check failover threshold
        if self.failure_count >= self.config.failover_threshold:
            # Check if enough time has passed since last failover
            if time.time() - self.last_failover_time > 300:  # 5 minutes
                return True
        
        return False
    
    def perform_failover(self) -> Optional[str]:
        """Perform failover to next available region"""
        if not self.should_failover():
            return None
        
        # Find next healthy region by priority
        sorted_regions = sorted(self.config.regions, key=lambda r: r.priority)
        
        for region_config in sorted_regions:
            if (region_config.region_name != self.current_region and 
                region_config.status == RegionStatus.ACTIVE and
                self.check_region_health(region_config.region_name)):
                
                old_region = self.current_region
                self.current_region = region_config.region_name
                self.failure_count = 0
                self.last_failover_time = time.time()
                
                logger.warning(f"Failover from {old_region} to {self.current_region}")
                return self.current_region
        
        logger.error("No healthy regions available for failover")
        return None
    
    def get_region_endpoints(self) -> Dict[str, Dict[str, str]]:
        """Get endpoints for all regions"""
        endpoints = {}
        for region_config in self.config.regions:
            endpoints[region_config.region_name] = {
                "api_gateway_url": region_config.api_gateway_url or "",
                "artifacts_bucket": region_config.artifacts_bucket or "",
                "runs_table": region_config.runs_table or "",
                "ecs_cluster": region_config.ecs_cluster or "",
                "status": region_config.status.value,
                "health_status": region_config.health_status,
                "last_health_check": region_config.last_health_check
            }
        return endpoints
    
    def replicate_data(self, source_region: str, target_region: str, data_type: str) -> bool:
        """Replicate data between regions"""
        try:
            if data_type == "dynamodb":
                return self._replicate_dynamodb_data(source_region, target_region)
            elif data_type == "s3":
                return self._replicate_s3_data(source_region, target_region)
            else:
                logger.error(f"Unsupported data type for replication: {data_type}")
                return False
        except Exception as e:
            logger.error(f"Data replication failed from {source_region} to {target_region}: {e}")
            return False
    
    def _replicate_dynamodb_data(self, source_region: str, target_region: str) -> bool:
        """Replicate DynamoDB data between regions"""
        source_config = self.get_region_config(source_region)
        target_config = self.get_region_config(target_region)
        
        if not source_config or not target_config or not source_config.runs_table or not target_config.runs_table:
            return False
        
        try:
            # Scan source table
            source_dynamodb = boto3.resource('dynamodb', region_name=source_region)
            target_dynamodb = boto3.resource('dynamodb', region_name=target_region)
            
            source_table = source_dynamodb.Table(source_config.runs_table)
            target_table = target_dynamodb.Table(target_config.runs_table)
            
            # Scan and replicate recent items (last 24 hours)
            cutoff_time = int(time.time()) - 86400
            
            response = source_table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('timestamp').gte(cutoff_time)
            )
            
            for item in response['Items']:
                target_table.put_item(Item=item)
            
            logger.info(f"Replicated {len(response['Items'])} DynamoDB items from {source_region} to {target_region}")
            return True
            
        except Exception as e:
            logger.error(f"DynamoDB replication failed: {e}")
            return False
    
    def _replicate_s3_data(self, source_region: str, target_region: str) -> bool:
        """Replicate S3 data between regions"""
        source_config = self.get_region_config(source_region)
        target_config = self.get_region_config(target_region)
        
        if not source_config or not target_config or not source_config.artifacts_bucket or not target_config.artifacts_bucket:
            return False
        
        try:
            source_s3 = boto3.client('s3', region_name=source_region)
            target_s3 = boto3.client('s3', region_name=target_region)
            
            # List objects in source bucket
            response = source_s3.list_objects_v2(Bucket=source_config.artifacts_bucket)
            
            if 'Contents' not in response:
                return True
            
            # Copy recent objects (last 24 hours)
            cutoff_time = time.time() - 86400
            
            for obj in response['Contents']:
                if obj['LastModified'].timestamp() > cutoff_time:
                    copy_source = {
                        'Bucket': source_config.artifacts_bucket,
                        'Key': obj['Key']
                    }
                    
                    target_s3.copy_object(
                        CopySource=copy_source,
                        Bucket=target_config.artifacts_bucket,
                        Key=obj['Key']
                    )
            
            logger.info(f"Replicated S3 objects from {source_region} to {target_region}")
            return True
            
        except Exception as e:
            logger.error(f"S3 replication failed: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get multi-region status"""
        return {
            "current_region": self.current_region,
            "failure_count": self.failure_count,
            "last_failover_time": self.last_failover_time,
            "failover_enabled": self.config.failover_enabled,
            "regions": self.get_region_endpoints(),
            "health_status": self.check_all_regions_health()
        }

# Global multi-region manager instance
_multi_region_manager: Optional[MultiRegionManager] = None

def get_multi_region_manager() -> Optional[MultiRegionManager]:
    """Get global multi-region manager instance"""
    return _multi_region_manager

def initialize_multi_region(config: MultiRegionConfig) -> MultiRegionManager:
    """Initialize multi-region manager"""
    global _multi_region_manager
    _multi_region_manager = MultiRegionManager(config)
    return _multi_region_manager

def get_current_region() -> str:
    """Get current active region"""
    manager = get_multi_region_manager()
    if manager:
        return manager.get_active_region()
    return "us-east-1"  # Default fallback

def check_and_failover() -> Optional[str]:
    """Check health and perform failover if needed"""
    manager = get_multi_region_manager()
    if manager:
        return manager.perform_failover()
    return None
