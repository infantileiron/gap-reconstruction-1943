from src.services import batch_review as service
def list_items(): return service.list_batches()
def create(data,user): return service.create(data,user)
def detail(id): return service.detail(id)
def resume(id): return service.execute(id)
