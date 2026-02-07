package main

deny[msg] {
  db := input.resource.aws_db_instance[_]
  db.publicly_accessible == true
  msg := "RDS instances must set publicly_accessible to false"
}

deny[msg] {
  db := input.resource.aws_db_instance[_]
  db.storage_encrypted != true
  msg := "RDS instances must enable storage_encrypted"
}

deny[msg] {
  db := input.resource.aws_db_instance[_]
  is_boolean(db.deletion_protection)
  db.deletion_protection == false
  msg := "RDS instances must enable deletion_protection"
}

deny[msg] {
  db := input.resource.aws_db_instance[_]
  db.skip_final_snapshot == true
  msg := "RDS instances must keep skip_final_snapshot=false"
}

deny[msg] {
  redis := input.resource.aws_elasticache_replication_group[_]
  redis.at_rest_encryption_enabled != "${var.redis_at_rest_encryption_enabled}"
  msg := "ElastiCache at-rest encryption must be controlled by terraform variable"
}

deny[msg] {
  redis := input.resource.aws_elasticache_replication_group[_]
  redis.transit_encryption_enabled != "${var.redis_transit_encryption_enabled}"
  msg := "ElastiCache transit encryption must be controlled by terraform variable"
}

deny[msg] {
  sg_name := object.keys(input.resource.aws_security_group)[_]
  sg := input.resource.aws_security_group[sg_name]
  ingress := ingress_rule(sg)[_]
  ingress.cidr_blocks[_] == "0.0.0.0/0"
  ingress.from_port <= 5432
  ingress.to_port >= 5432
  msg := sprintf("Security group %s exposes PostgreSQL port to the internet", [sg_name])
}

deny[msg] {
  sg_name := object.keys(input.resource.aws_security_group)[_]
  sg := input.resource.aws_security_group[sg_name]
  ingress := ingress_rule(sg)[_]
  ingress.cidr_blocks[_] == "0.0.0.0/0"
  ingress.from_port <= 6379
  ingress.to_port >= 6379
  msg := sprintf("Security group %s exposes Redis port to the internet", [sg_name])
}

deny[msg] {
  lb := input.resource.aws_lb[_]
  lb.drop_invalid_header_fields != true
  msg := "ALB must enable drop_invalid_header_fields"
}

deny[msg] {
  input.variable.redis_at_rest_encryption_enabled["default"] != true
  msg := "redis_at_rest_encryption_enabled should default to true"
}

deny[msg] {
  input.variable.redis_transit_encryption_enabled["default"] != true
  msg := "redis_transit_encryption_enabled should default to true"
}

deny[msg] {
  input.variable.db_deletion_protection["default"] != true
  msg := "db_deletion_protection should default to true"
}

deny[msg] {
  input.variable.db_skip_final_snapshot["default"] != false
  msg := "db_skip_final_snapshot should default to false"
}

ingress_rule(sg) = rules {
  is_array(sg.ingress)
  rules := sg.ingress
}

ingress_rule(sg) = rules {
  is_object(sg.ingress)
  rules := [sg.ingress]
}
