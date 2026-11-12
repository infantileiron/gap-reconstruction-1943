import {request} from './client';import type {Mask} from '../types/entities';export const list=()=>request<Mask[]>('/masks');export const create=(data:unknown)=>request<Mask>('/masks','POST',data);
