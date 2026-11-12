import {request} from './client';import type {BatchReview} from '../types/entities';
export const list=()=>request<BatchReview[]>('/batch-reviews');
export const create=(data:unknown)=>request<BatchReview>('/batch-reviews','POST',data);
export const detail=(id:string)=>request<BatchReview>('/batch-reviews/'+id);
export const resume=(id:string)=>request<BatchReview>('/batch-reviews/'+id+'/resume','POST');
