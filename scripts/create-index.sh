host="http://bioghost3.usc.edu:9200"

curl -XPUT -H "Content-Type: application/json" $host/_cluster/settings -d '{ "transient": { "cluster.routing.allocation.disk.threshold_enabled": false } }'
curl -XPUT -H "Content-Type: application/json" $host/_all/_settings -d '{"index.blocks.read_only_allow_delete": null}'

curl -X PUT $host/annoq-annotations-tm-20251208 -H 'Content-Type: application/json' -d'
{
  "settings": {
    "number_of_shards": 200,
    "number_of_replicas" : 0,
    "refresh_interval" : -1
  }
}
'