from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dbt_semguard.models import (
    DimensionContract,
    EntityContract,
    MeasureContract,
    MetricContract,
    SemanticContract,
    SemanticModelContract,
)
from dbt_semguard.normalization import (
    _mapping_values,
    _nested_mapping_get,
    _normalize_filter_value,
    _normalize_input_metrics,
    _normalize_metric_ref,
    _normalize_value,
)

def extract_contract_from_manifest(manifest_path: str | Path) -> SemanticContract:
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if _looks_like_plain_dbt_manifest(payload):
        raise ValueError(
            "Unsupported dbt manifest.json artifact. Pass a dbt semantic_manifest.json artifact instead."
        )
    if "semantic_models" not in payload or "metrics" not in payload:
        raise ValueError(
            "Manifest input must be a dbt semantic_manifest.json artifact with 'semantic_models' and 'metrics'."
        )
    if _looks_like_semantic_manifest_payload(payload):
        return _build_contract_from_semantic_manifest_payload(payload)
    return _build_contract_from_compact_manifest_payload(payload)

def _build_contract_from_compact_manifest_payload(payload: dict[str, Any]) -> SemanticContract:
    semantic_models: dict[str, SemanticModelContract] = {}
    metrics: dict[str, MetricContract] = {}

    for node in _mapping_values(payload.get("semantic_models", {})):
        name = node["name"]
        semantic_models[name] = SemanticModelContract(
            name=name,
            model_name=node["model_name"],
            agg_time_dimension=node.get("agg_time_dimension"),
            entities={
                entity["name"]: EntityContract(
                    name=entity["name"],
                    type=entity["type"],
                    expr=entity.get("expr") or entity["name"],
                )
                for entity in node.get("entities", [])
            },
            dimensions={
                dimension["name"]: DimensionContract(
                    name=dimension["name"],
                    type=dimension["type"],
                    expr=dimension.get("expr") or dimension["name"],
                    granularity=dimension.get("granularity"),
                )
                for dimension in node.get("dimensions", [])
            },
            measures={
                measure["name"]: _build_manifest_measure_contract(measure)
                for measure in node.get("measures", []) or []
                if isinstance(measure, dict) and "name" in measure
            },
        )

    for node in _mapping_values(payload.get("metrics", {})):
        metric = MetricContract.from_dict(node | {"owner_model": node.get("owner_model")})
        metrics[metric.name] = metric

    return SemanticContract(semantic_models=semantic_models, metrics=metrics)

def _build_contract_from_semantic_manifest_payload(payload: dict[str, Any]) -> SemanticContract:
    if "project_configuration" not in payload:
        raise ValueError("semantic_manifest.json is missing required 'project_configuration' section")

    semantic_models: dict[str, SemanticModelContract] = {}
    metrics: dict[str, MetricContract] = {}
    measures_by_model: dict[str, dict[str, dict[str, Any]]] = {}
    model_default_agg_time_dimensions: dict[str, str | None] = {}

    for node in _mapping_values(payload.get("semantic_models", {})):
        name = node["name"]
        default_agg_time_dimension = _nested_mapping_get(node, "defaults", "agg_time_dimension")
        measure_payloads = {
            measure["name"]: measure
            for measure in node.get("measures", []) or []
            if isinstance(measure, dict) and "name" in measure
        }
        semantic_models[name] = SemanticModelContract(
            name=name,
            model_name=_semantic_model_backing_model_name(node),
            agg_time_dimension=default_agg_time_dimension,
            entities={
                entity["name"]: EntityContract(
                    name=entity["name"],
                    type=entity["type"],
                    expr=entity.get("expr") or entity["name"],
                )
                for entity in node.get("entities", [])
            },
            dimensions={
                dimension["name"]: DimensionContract(
                    name=dimension["name"],
                    type=dimension["type"],
                    expr=dimension.get("expr") or dimension["name"],
                    granularity=_nested_mapping_get(dimension, "type_params", "time_granularity")
                    or dimension.get("granularity"),
                )
                for dimension in node.get("dimensions", [])
            },
            measures={
                measure_name: _build_manifest_measure_contract(measure_payload)
                for measure_name, measure_payload in measure_payloads.items()
            },
        )
        model_default_agg_time_dimensions[name] = default_agg_time_dimension
        measures_by_model[name] = measure_payloads

    for node in _mapping_values(payload.get("metrics", {})):
        metric = _build_metric_contract_from_semantic_manifest(
            node,
            measures_by_model=measures_by_model,
            model_default_agg_time_dimensions=model_default_agg_time_dimensions,
        )
        metrics[metric.name] = metric

    return SemanticContract(semantic_models=semantic_models, metrics=metrics)

def _build_manifest_measure_contract(payload: dict[str, Any]) -> MeasureContract:
    name = payload["name"]
    return MeasureContract(
        name=name,
        agg=payload.get("agg"),
        expr=str(payload.get("expr") or name),
        agg_time_dimension=payload.get("agg_time_dimension"),
        non_additive_dimension=payload.get("non_additive_dimension"),
    )

def _build_metric_contract_from_semantic_manifest(
    payload: dict[str, Any],
    measures_by_model: dict[str, dict[str, dict[str, Any]]],
    model_default_agg_time_dimensions: dict[str, str | None],
    source_file: str | None = None,
) -> MetricContract:
    type_params = payload.get("type_params") or {}
    metric_aggregation_params = type_params.get("metric_aggregation_params") or {}
    cumulative_type_params = type_params.get("cumulative_type_params") or {}
    conversion_type_params = type_params.get("conversion_type_params") or {}
    metric_type = str(payload["type"])
    owner_model = metric_aggregation_params.get("semantic_model")
    measure_name = _normalize_metric_ref(type_params.get("measure"))
    measure_payload = None

    if metric_type == "simple":
        if not owner_model:
            raise ValueError(
                f"semantic_manifest.json simple metric '{payload['name']}' is missing "
                "'type_params.metric_aggregation_params.semantic_model'"
            )
        if not measure_name:
            raise ValueError(
                f"semantic_manifest.json simple metric '{payload['name']}' is missing 'type_params.measure'"
            )
        measure_payload = measures_by_model.get(owner_model, {}).get(measure_name)
        if measure_payload is None:
            raise ValueError(
                f"semantic_manifest.json simple metric '{payload['name']}' references measure "
                f"'{measure_name}' in semantic model '{owner_model}', but that measure was not found."
            )

    expr = _normalize_value(payload.get("expr"))
    if metric_type == "simple" and measure_payload is not None:
        expr = _normalize_value(measure_payload.get("expr") or measure_name)
    elif metric_type == "derived":
        expr = _normalize_value(type_params.get("expr"))

    agg = _normalize_value(metric_aggregation_params.get("agg"))
    if agg is None and measure_payload is not None:
        agg = _normalize_value(measure_payload.get("agg"))

    agg_time_dimension = metric_aggregation_params.get("agg_time_dimension")
    if agg_time_dimension is None and measure_payload is not None:
        agg_time_dimension = measure_payload.get("agg_time_dimension")
    if agg_time_dimension == model_default_agg_time_dimensions.get(owner_model):
        agg_time_dimension = None

    non_additive_dimension = metric_aggregation_params.get("non_additive_dimension")
    if non_additive_dimension is None and measure_payload is not None:
        non_additive_dimension = measure_payload.get("non_additive_dimension")

    return MetricContract(
        name=payload["name"],
        metric_type=metric_type,
        label=payload.get("label"),
        agg=agg,
        expr=expr,
        filter=_normalize_filter_value(payload.get("filter")),
        agg_time_dimension=agg_time_dimension,
        numerator=_normalize_metric_ref(type_params.get("numerator")),
        denominator=_normalize_metric_ref(type_params.get("denominator")),
        input_metrics=_normalize_input_metrics(type_params.get("metrics") or payload.get("input_metrics")),
        input_metric=_normalize_metric_ref(type_params.get("input_metric") or type_params.get("measure") or payload.get("input_metric"))
        if metric_type == "cumulative"
        else None,
        window=_normalize_value(cumulative_type_params.get("window") or type_params.get("window") or payload.get("window"))
        if metric_type == "cumulative"
        else None,
        grain_to_date=_normalize_value(
            cumulative_type_params.get("grain_to_date") or type_params.get("grain_to_date") or payload.get("grain_to_date")
        )
        if metric_type == "cumulative"
        else None,
        period_agg=_normalize_value(
            cumulative_type_params.get("period_agg") or type_params.get("period_agg") or payload.get("period_agg")
        )
        if metric_type == "cumulative"
        else None,
        entity=_normalize_metric_ref(conversion_type_params.get("entity") or type_params.get("entity") or payload.get("entity"))
        if metric_type == "conversion"
        else None,
        calculation=_normalize_value(
            conversion_type_params.get("calculation") or type_params.get("calculation") or payload.get("calculation")
        )
        if metric_type == "conversion"
        else None,
        base_metric=_normalize_metric_ref(
            conversion_type_params.get("base_metric")
            or conversion_type_params.get("base_measure")
            or type_params.get("base_metric")
            or payload.get("base_metric")
        )
        if metric_type == "conversion"
        else None,
        conversion_metric=_normalize_metric_ref(
            conversion_type_params.get("conversion_metric")
            or conversion_type_params.get("conversion_measure")
            or type_params.get("conversion_metric")
            or payload.get("conversion_metric")
        )
        if metric_type == "conversion"
        else None,
        constant_properties=_normalize_value(
            conversion_type_params.get("constant_properties")
            or type_params.get("constant_properties")
            or payload.get("constant_properties")
        )
        if metric_type == "conversion"
        else None,
        non_additive_dimension=non_additive_dimension,
        owner_model=owner_model,
        source=None,
    )

def _looks_like_plain_dbt_manifest(payload: dict[str, Any]) -> bool:
    metadata = payload.get("metadata")
    schema_version = metadata.get("dbt_schema_version") if isinstance(metadata, dict) else None
    return ("nodes" in payload or "parent_map" in payload) and (
        isinstance(schema_version, str) and "/manifest/" in schema_version or "semantic_models" not in payload
    )

def _looks_like_semantic_manifest_payload(payload: dict[str, Any]) -> bool:
    semantic_models = _mapping_values(payload.get("semantic_models"))
    if not semantic_models:
        return False
    first_model = semantic_models[0]
    return any(key in first_model for key in ("node_relation", "defaults", "measures"))

def _semantic_model_backing_model_name(node: dict[str, Any]) -> str:
    node_relation = node.get("node_relation")
    if isinstance(node_relation, dict):
        for key in ("alias", "relation_name"):
            value = node_relation.get(key)
            if value:
                return str(value)
    return str(node.get("model_name") or node["name"])