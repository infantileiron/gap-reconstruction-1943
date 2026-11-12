import type {User} from '../types/entities';
export function savedUser():User|null {try{return JSON.parse(sessionStorage.getItem('gap-user')||'null')}catch{return null}}
export function saveSession(token:string,user:User){sessionStorage.setItem('gap-token',token);sessionStorage.setItem('gap-user',JSON.stringify(user))}
export function clearSession(){sessionStorage.removeItem('gap-token');sessionStorage.removeItem('gap-user')}
