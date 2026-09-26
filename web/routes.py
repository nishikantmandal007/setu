import controller


# every URL the app answers, and the controller that handles it
def register(app):
    app.add_url_rule("/", view_func=controller.page)
    app.add_url_rule("/schema", view_func=controller.schema)
    app.add_url_rule("/analyse", view_func=controller.analyse, methods=["POST"])
    app.add_url_rule("/progress/<job_id>", view_func=controller.progress)
    app.add_url_rule("/result/<job_id>", view_func=controller.result)
    app.add_url_rule("/critical-loads/<job_id>.csv", view_func=controller.critical_loads_file)
    app.add_url_rule("/shared/<name>", view_func=controller.shared)
