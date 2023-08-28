class Hooks(object):
    # post_service_init(worker): Called just after a worker has initialized the application.
    # post_worker_fork(server, worker): Called just after a worker has been forked.
    # post_worker_exit(server, worker): Called just after a worker has been exited, in the worker process.
    def __init__(
        self, post_service_init=None, post_worker_fork=None, post_worker_exit=None
    ):
        super().__init__()
        self.post_service_init = (
            post_service_init if post_service_init else self.__default_post_service_init
        )
        self.post_worker_fork = (
            post_worker_fork if post_worker_fork else self.__default_post_worker_fork
        )
        self.post_worker_exit = (
            post_worker_exit if post_worker_exit else self.__default_post_worker_exit
        )

    def __default_post_service_init(self, worker):
        pass

    def __default_post_worker_fork(self, server, worker):
        pass

    def __default_post_worker_exit(self, server, worker):
        pass
