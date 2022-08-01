from supersetapiclient.client import SupersetClient

client = SupersetClient(
    host="https://dev.superset.materialplus.io/",
    username="hbalian",
    password="XO5PFYZIeEo9FT1@",
)


client.base_url

dashboards = client.dashboards.find()

dashboard = dashboards[0]
dashboard.get_charts()
dashboard.base_url
dashboard.id
dashboard.export('/users/hragbalian/desktop/')
dashboard.export_url




dashboard.field_names()


response = client.get(dashboard.export_url, params={
    "q": [dashboard.id]  # Object must have an id field to be exported
})
response.raise_for_status()

dashboard.import_url

chart.base_url
charts = client.charts.find()
charts.count()
chart = charts[0]


chart.import_url
chart.export_url

client.
chart.export('/users/hragbalian/desktop/out.zip')
