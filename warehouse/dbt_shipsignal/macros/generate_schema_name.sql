{#
  by default dbt prefixes custom schemas with the target schema (public_marts).
  plain "staging" and "marts" are easier to query from the api and from tableau.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
